from homeassistant.components.number import RestoreNumber
from .const import (
    DOMAIN,
    CONF_FIXED_THRESHOLD,
    CONF_LOW_TARGET_PER_DAY,
    CONF_LOW_TIME_WINDOW,
    CONF_HIGH_TARGET_PER_DAY,
    CONF_HIGH_TIME_WINDOW,
)


async def async_setup_entry(hass, entry, async_add_entities):
    async_add_entities([
        NordpoolPlannerNumber(
            entry=entry,
            name="Accepted low cost threshold",
            key=CONF_FIXED_THRESHOLD,
            min_val=0.000,
            max_val=0.200,
            step=0.005,
            unit="EUR/kWh",
            icon="mdi:currency-eur",
            precision=3,
        ),
        NordpoolPlannerNumber(
            entry=entry,
            name="Low cost per day target",
            key=CONF_LOW_TARGET_PER_DAY,
            min_val=1,
            max_val=15,
            step=1,
            unit="h",
            icon="mdi:target",
            precision=0,
        ),
        NordpoolPlannerDurationNumber(
            entry=entry,
            name="Low cost time window",
            key=CONF_LOW_TIME_WINDOW,
            min_val=0.25,
            max_val=3.0,
            step=0.25,
            icon="mdi:clock-outline",
        ),
        NordpoolPlannerNumber(
            entry=entry,
            name="High cost per day target",
            key=CONF_HIGH_TARGET_PER_DAY,
            min_val=1,
            max_val=15,
            step=1,
            unit="h",
            icon="mdi:target-account",
            precision=0,
        ),
        NordpoolPlannerDurationNumber(
            entry=entry,
            name="High cost time window",
            key=CONF_HIGH_TIME_WINDOW,
            min_val=0.25,
            max_val=3.0,
            step=0.25,
            icon="mdi:clock-alert-outline",
        ),
    ], True)


class NordpoolPlannerNumber(RestoreNumber):
    _attr_has_entity_name = True

    def __init__(self, entry, name, key, min_val, max_val, step, unit, icon, precision=None):
        self._entry = entry
        self._attr_name = name
        self._key = key
        self._attr_native_min_value = min_val
        self._attr_native_max_value = max_val
        self._attr_native_step = step
        self._attr_native_unit_of_measurement = unit
        self._attr_icon = icon
        self._attr_unique_id = f"{entry.entry_id}_{key}"

        if precision is not None:
            self._attr_display_precision = precision

        raw_val = entry.data.get(key, min_val)
        self._attr_native_value = round(float(raw_val), precision) if precision is not None else float(raw_val)

    @property
    def device_info(self):
        return {
            "identifiers": {(DOMAIN, self._entry.entry_id)},
            "name": "Nordpool Smart Planner",
            "manufacturer": "Nordpool",
            "model": "Smart Planner",
        }

    async def async_added_to_hass(self):
        await super().async_added_to_hass()
        last_number_data = await self.async_get_last_number_data()
        if last_number_data and last_number_data.native_value is not None:
            if hasattr(self, "_attr_display_precision") and self._attr_display_precision is not None:
                self._attr_native_value = round(float(last_number_data.native_value), self._attr_display_precision)
            else:
                self._attr_native_value = float(last_number_data.native_value)

    async def async_set_native_value(self, value: float) -> None:
        if hasattr(self, "_attr_display_precision") and self._attr_display_precision is not None:
            value = round(value, self._attr_display_precision)

        self._attr_native_value = value
        self.async_write_ha_state()

        new_data = {**self._entry.data, self._key: value}
        self.hass.config_entries.async_update_entry(self._entry, data=new_data)

        # Zibensātra atjaunošana visiem sensoriem
        for st in self.hass.states.async_all("sensor"):
            if st.entity_id.startswith("sensor.") and "nordpool_smart_planner" in st.entity_id:
                self.hass.async_create_task(
                    self.hass.services.async_call("homeassistant", "update_entity", {"entity_id": st.entity_id})
                )


class NordpoolPlannerDurationNumber(NordpoolPlannerNumber):
    def __init__(self, entry, name, key, min_val, max_val, step, icon):
        super().__init__(entry, name, key, min_val, max_val, step, None, icon, precision=2)

    @property
    def native_unit_of_measurement(self) -> str:
        val = self.native_value or 0.25
        hours = int(val)
        minutes = int(round((val - hours) * 60))
        if hours > 0 and minutes > 0:
            return f"({hours}h {minutes}min)"
        elif hours > 0:
            return "stundas"
        else:
            return f"({minutes} min)"
