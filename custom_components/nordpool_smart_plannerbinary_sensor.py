from datetime import timedelta
from homeassistant.components.binary_sensor import BinarySensorEntity, BinarySensorDeviceClass
from homeassistant.util import dt as dt_util

from .const import DOMAIN, CONF_LOW_TIME_WINDOW, CONF_HIGH_TIME_WINDOW


async def async_setup_entry(hass, entry, async_add_entities):
    async_add_entities([
        NordpoolPlannerBinarySensor(hass, entry, "Nordpool low", "low_cost"),
        NordpoolPlannerBinarySensor(hass, entry, "Nordpool high", "high_cost"),
    ], True)


class NordpoolPlannerBinarySensor(BinarySensorEntity):
    _attr_has_entity_name = True

    def __init__(self, hass, entry, name, sensor_type):
        self.hass = hass
        self._entry = entry
        self._attr_name = name
        self._sensor_type = sensor_type
        self._attr_unique_id = f"{entry.entry_id}_binary_{sensor_type}"
        self._attr_device_class = BinarySensorDeviceClass.RUNNING
        self._is_on = False

    @property
    def device_info(self):
        return {
            "identifiers": {(DOMAIN, self._entry.entry_id)},
            "name": "Nordpool Smart Planner",
            "manufacturer": "Nordpool",
            "model": "Smart Planner",
        }

    @property
    def is_on(self):
        return self._is_on

    def update(self):
        parent_state = None
        for st in self.hass.states.async_all("sensor"):
            if st.entity_id.endswith(self._sensor_type):
                parent_state = st
                break

        if not parent_state:
            self._is_on = False
            return

        scheduled_times_str = parent_state.attributes.get("scheduled_times", "")
        if scheduled_times_str in ["No data", "Waiting for Nordpool data", ""]:
            self._is_on = False
            return

        periods = scheduled_times_str.split(", ")
        now_dt = dt_util.now()

        is_active = False
        for p in periods:
            p_dt = dt_util.parse_datetime(p)
            if p_dt and p_dt <= now_dt < (p_dt + timedelta(minutes=15)):
                is_active = True
                break

        self._is_on = is_active
