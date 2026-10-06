import logging
from datetime import datetime, timedelta
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.event import async_track_state_change_event
from homeassistant.util import dt as dt_util

from .const import (
    DOMAIN,
    CONF_NORDPOOL_ENTITY,
    CONF_FIXED_THRESHOLD,
    CONF_LOW_TARGET_PER_DAY,
    CONF_LOW_TIME_WINDOW,
    CONF_HIGH_TARGET_PER_DAY,
    CONF_HIGH_TIME_WINDOW,
)

_LOGGER = logging.getLogger(__name__)


def extract_dt(dt_input):
    if dt_input is None:
        return None
    if isinstance(dt_input, datetime):
        return dt_util.as_local(dt_input)
    if isinstance(dt_input, str):
        parsed = dt_util.parse_datetime(dt_input)
        if parsed:
            return dt_util.as_local(parsed)
    return None


async def async_setup_entry(hass, entry, async_add_entities):
    nordpool_entity = entry.data.get(CONF_NORDPOOL_ENTITY)

    entities = [
        NordpoolPlannerSensor(hass, entry, nordpool_entity, "Low cost", "low_cost"),
        NordpoolPlannerSensor(hass, entry, nordpool_entity, "High cost", "high_cost"),
    ]

    async_add_entities(entities, True)


class NordpoolPlannerSensor(Entity):
    _attr_has_entity_name = True

    def __init__(self, hass, entry, nordpool_entity, name, sensor_type):
        self.hass = hass
        self._entry = entry
        self._nordpool_entity = nordpool_entity
        self._attr_name = name
        self._sensor_type = sensor_type
        self._attr_unique_id = f"{entry.entry_id}_{sensor_type}"
        self._scheduled_times = []

    @property
    def device_info(self):
        return {
            "identifiers": {(DOMAIN, self._entry.entry_id)},
            "name": "Nordpool Smart Planner",
            "manufacturer": "Nordpool",
            "model": "Smart Planner",
        }

    @property
    def state(self):
        return len(self._scheduled_times)

    @property
    def extra_state_attributes(self):
        return {
            "scheduled_times": ", ".join(self._scheduled_times) if self._scheduled_times else "No data"
        }

    async def async_added_to_hass(self):
        await super().async_added_to_hass()

        if self._nordpool_entity:
            self.async_on_remove(
                async_track_state_change_event(
                    self.hass, [self._nordpool_entity], self._async_on_nordpool_update
                )
            )

    async def _async_on_nordpool_update(self, event):
        self.async_schedule_update_ha_state(True)

    async def async_update(self):
        nordpool_state = self.hass.states.get(self._nordpool_entity)
        if not nordpool_state:
            return

        raw_today = nordpool_state.attributes.get("raw_today", []) or []
        raw_tomorrow = nordpool_state.attributes.get("raw_tomorrow", []) or []
        raw = raw_today + raw_tomorrow

        if not raw:
            self._scheduled_times = []
            return

        options = {**self._entry.data, **self._entry.options}
        fixed_threshold = float(options.get(CONF_FIXED_THRESHOLD, 0.05))

        if self._sensor_type == "low_cost":
            target_per_day = int(options.get(CONF_LOW_TARGET_PER_DAY, 4))
            window_hours = float(options.get(CONF_LOW_TIME_WINDOW, 1.0))
        else:
            target_per_day = int(options.get(CONF_HIGH_TARGET_PER_DAY, 3))
            window_hours = float(options.get(CONF_HIGH_TIME_WINDOW, 0.5))

        parsed_entries = []
        for item in raw:
            if isinstance(item, dict):
                t_val = extract_dt(item.get("start"))
                p_val = item.get("value")
                if t_val is not None and p_val is not None:
                    parsed_entries.append((t_val, float(p_val)))

        if not parsed_entries:
            return

        now_dt = dt_util.now()
        today_start = now_dt.replace(hour=0, minute=0, second=0, microsecond=0)
        tomorrow_start = today_start + timedelta(days=1)

        end_of_data = parsed_entries[-1][0]

        has_tomorrow = end_of_data >= (tomorrow_start + timedelta(hours=22))
        if not has_tomorrow:
            start_filter = today_start
            hours_needed = target_per_day
        else:
            start_filter = now_dt.replace(minute=0, second=0, microsecond=0)
            remaining_hours = (end_of_data - start_filter).total_seconds() / 3600
            hours_needed = max(1, int(round((remaining_hours / 24) * target_per_day)))

        target_intervals = int(hours_needed * 4)
        intervals_needed = max(1, int(round(window_hours / 0.25)))

        all_sub_indices = set()

        if self._sensor_type == "low_cost":
            # 1. Low Cost: Fiksētais slieksnis
            selected_windows = []
            used_indices = set()

            for i in range(len(parsed_entries) - intervals_needed + 1):
                t_start = parsed_entries[i][0]
                if t_start + timedelta(hours=window_hours) > start_filter:
                    avg_p = sum(parsed_entries[k][1] for k in range(i, i + intervals_needed)) / intervals_needed

                    if avg_p <= fixed_threshold:
                        check_indices = set(range(i, i + intervals_needed))
                        if not check_indices.intersection(used_indices):
                            selected_windows.append(i)
                            used_indices.update(check_indices)
                            all_sub_indices.update(check_indices)

            # 2. Low Cost: Lētākās papildu stundas
            all_windows = []
            for i in range(len(parsed_entries) - intervals_needed + 1):
                t_start = parsed_entries[i][0]
                if t_start + timedelta(hours=window_hours) > start_filter:
                    avg_p = sum(parsed_entries[k][1] for k in range(i, i + intervals_needed)) / intervals_needed
                    score = avg_p - 0.001 if (t_start <= now_dt < t_start + timedelta(hours=window_hours)) else avg_p
                    all_windows.append({"idx": i, "p": score})

            sorted_windows = sorted(all_windows, key=lambda x: x["p"])

            for w in sorted_windows:
                if len(all_sub_indices) < target_intervals:
                    check_indices = set(range(w["idx"], w["idx"] + intervals_needed))
                    if not check_indices.intersection(used_indices):
                        used_indices.update(check_indices)
                        all_sub_indices.update(check_indices)

        else:
            # 1. High Cost: Atlasām dārgākos logus pa nepārtrauktiem 'High cost duration' laikiem
            all_windows = []
            for i in range(len(parsed_entries) - intervals_needed + 1):
                t_start = parsed_entries[i][0]
                if t_start + timedelta(hours=window_hours) > start_filter:
                    avg_p = sum(parsed_entries[k][1] for k in range(i, i + intervals_needed)) / intervals_needed
                    if avg_p > fixed_threshold:
                        all_windows.append({"idx": i, "p": avg_p})

            sorted_windows = sorted(all_windows, key=lambda x: x["p"], reverse=True)
            used_indices = set()

            for w in sorted_windows:
                if len(all_sub_indices) < target_intervals:
                    check_indices = set(range(w["idx"], w["idx"] + intervals_needed))
                    if not check_indices.intersection(used_indices):
                        used_indices.update(check_indices)
                        all_sub_indices.update(check_indices)

            # 2. High Cost: Papildinām ar atsevišķiem dārgākajiem 15min intervāliem, ja ar nepārtrauktiem logiem trūkst līdz mērķim
            if len(all_sub_indices) < target_intervals:
                single_intervals = []
                for i in range(len(parsed_entries)):
                    t_start = parsed_entries[i][0]
                    if t_start > start_filter and parsed_entries[i][1] > fixed_threshold:
                        single_intervals.append({"idx": i, "p": parsed_entries[i][1]})

                sorted_singles = sorted(single_intervals, key=lambda x: x["p"], reverse=True)
                for s in sorted_singles:
                    if len(all_sub_indices) < target_intervals:
                        all_sub_indices.add(s["idx"])

        sorted_sub_indices = sorted(list(all_sub_indices))
        self._scheduled_times = [parsed_entries[i][0].isoformat() for i in sorted_sub_indices]