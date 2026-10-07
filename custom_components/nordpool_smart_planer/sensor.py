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


def calculate_planner_schedules(raw, options, now_dt):
    """Galvenais dzinējs, kas aprēķina abus sensorus kopā un izslēdz pārklāšanos."""
    fixed_threshold = float(options.get(CONF_FIXED_THRESHOLD, 0.05))

    low_target_per_day = int(options.get(CONF_LOW_TARGET_PER_DAY, 4))
    low_window_hours = float(options.get(CONF_LOW_TIME_WINDOW, 1.0))

    high_target_per_day = int(options.get(CONF_HIGH_TARGET_PER_DAY, 3))
    high_window_hours = float(options.get(CONF_HIGH_TIME_WINDOW, 0.5))

    parsed_entries = []
    for item in raw:
        if isinstance(item, dict):
            t_val = extract_dt(item.get("start"))
            p_val = item.get("value")
            if t_val is not None and p_val is not None:
                parsed_entries.append((t_val, float(p_val)))

    if not parsed_entries:
        return [], []

    today_start = now_dt.replace(hour=0, minute=0, second=0, microsecond=0)
    tomorrow_start = today_start + timedelta(days=1)

    end_of_data = parsed_entries[-1][0]

    has_tomorrow = end_of_data >= (tomorrow_start + timedelta(hours=22))
    if not has_tomorrow:
        start_filter = today_start
        low_hours_needed = low_target_per_day
        high_hours_needed = high_target_per_day
    else:
        start_filter = now_dt.replace(minute=0, second=0, microsecond=0)
        remaining_hours = (end_of_data - start_filter).total_seconds() / 3600
        low_hours_needed = max(1, int(round((remaining_hours / 24) * low_target_per_day)))
        high_hours_needed = max(1, int(round((remaining_hours / 24) * high_target_per_day)))

    # --- 1. HIGH COST APRĒĶINS ---
    high_intervals_needed = max(1, int(round(high_window_hours / 0.25)))
    high_target_intervals = int(high_hours_needed * 4)

    high_sub_indices = set()
    high_used_indices = set()

    high_all_windows = []
    for i in range(len(parsed_entries) - high_intervals_needed + 1):
        t_start = parsed_entries[i][0]
        if t_start + timedelta(hours=high_window_hours) > start_filter:
            avg_p = sum(parsed_entries[k][1] for k in range(i, i + high_intervals_needed)) / high_intervals_needed
            if avg_p > fixed_threshold:
                high_all_windows.append({"idx": i, "p": avg_p})

    sorted_high_windows = sorted(high_all_windows, key=lambda x: x["p"], reverse=True)

    for w in sorted_high_windows:
        if len(high_sub_indices) < high_target_intervals:
            check_indices = set(range(w["idx"], w["idx"] + high_intervals_needed))
            if not check_indices.intersection(high_used_indices):
                high_used_indices.update(check_indices)
                high_sub_indices.update(check_indices)

    if len(high_sub_indices) < high_target_intervals:
        single_intervals = []
        for i in range(len(parsed_entries)):
            t_start = parsed_entries[i][0]
            if t_start > start_filter and parsed_entries[i][1] > fixed_threshold:
                single_intervals.append({"idx": i, "p": parsed_entries[i][1]})

        sorted_singles = sorted(single_intervals, key=lambda x: x["p"], reverse=True)
        for s in sorted_singles:
            if len(high_sub_indices) < high_target_intervals:
                high_sub_indices.add(s["idx"])

    # --- 2. LOW COST APRĒĶINS (BEZ HIGH COST INDEKSIEM) ---
    low_intervals_needed = max(1, int(round(low_window_hours / 0.25)))
    low_target_intervals = int(low_hours_needed * 4)

    low_sub_indices = set()
    low_used_indices = set(high_sub_indices)  # SVARĪGI: Aizliedzam izmantot High Cost laikus!

    # A. Fiksētais slieksnis
    for i in range(len(parsed_entries) - low_intervals_needed + 1):
        t_start = parsed_entries[i][0]
        if t_start + timedelta(hours=low_window_hours) > start_filter:
            check_indices = set(range(i, i + low_intervals_needed))
            # Pārbaudām, lai neviens no intervāliem neietilptu High Cost sarakstā
            if not check_indices.intersection(high_sub_indices):
                avg_p = sum(parsed_entries[k][1] for k in range(i, i + low_intervals_needed)) / low_intervals_needed
                if avg_p <= fixed_threshold:
                    if not check_indices.intersection(low_used_indices):
                        low_used_indices.update(check_indices)
                        low_sub_indices.update(check_indices)

    # B. Lētāko logu piemeklēšana
    low_all_windows = []
    for i in range(len(parsed_entries) - low_intervals_needed + 1):
        t_start = parsed_entries[i][0]
        if t_start + timedelta(hours=low_window_hours) > start_filter:
            check_indices = set(range(i, i + low_intervals_needed))
            if not check_indices.intersection(high_sub_indices):
                avg_p = sum(parsed_entries[k][1] for k in range(i, i + low_intervals_needed)) / low_intervals_needed
                score = avg_p - 0.001 if (t_start <= now_dt < t_start + timedelta(hours=low_window_hours)) else avg_p
                low_all_windows.append({"idx": i, "p": score})

    sorted_low_windows = sorted(low_all_windows, key=lambda x: x["p"])

    for w in sorted_low_windows:
        if len(low_sub_indices) < low_target_intervals:
            check_indices = set(range(w["idx"], w["idx"] + low_intervals_needed))
            if not check_indices.intersection(low_used_indices):
                low_used_indices.update(check_indices)
                low_sub_indices.update(check_indices)

    sorted_high_times = [parsed_entries[i][0].isoformat() for i in sorted(list(high_sub_indices))]
    sorted_low_times = [parsed_entries[i][0].isoformat() for i in sorted(list(low_sub_indices))]

    return sorted_low_times, sorted_high_times


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
        now_dt = dt_util.now()

        # Veicam aprēķinu abiem sensoriem kopā
        low_times, high_times = calculate_planner_schedules(raw, options, now_dt)

        if self._sensor_type == "low_cost":
            self._scheduled_times = low_times
        else:
            self._scheduled_times = high_times
