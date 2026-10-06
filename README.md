# Nordpool Smart Planner

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://github.com/hacs/default)

**Nordpool Smart Planner** is a Home Assistant custom component that automatically calculates and optimizes electricity consumption and curtailment schedules based on dynamic Nordpool spot prices (`raw_today` and `raw_tomorrow`).

It natively supports **15-minute price resolution**, fixed cost thresholds, and completely independent optimization algorithms for low-cost consumption periods (`Low cost`) and high-cost peak curtailment periods (`High cost`).

---

## 🚀 Key Features

- **Separate Low/High Cost Logic:**
  - **Low Cost Planner:** Finds optimal consecutive time windows for appliances like heat pumps, boilers, or EV chargers, while automatically capturing all interval prices below your `Accept cost` threshold.
  - **High Cost Planner:** Pinpoints peak price periods (e.g., 0.5h–1.0h windows) to pause or block high-load devices during expensive price spikes.
- **Dynamic Control Sliders (`number` entities):**
  - `Accept cost` — Fixed price threshold ($0.000$ to $0.300$ EUR/kWh with $0.005$ step precision).
  - `Low cost target` & `High cost target` — Daily target hours ($1$–$24\text{h}$).
  - `Low cost duration` & `High cost duration` — Minimum continuous window size ($0.25$ to $6.0\text{h}$).
- **ApexCharts Ready:** Stores granular 15-minute sub-intervals inside the `scheduled_times` attribute for seamless background plot highlighting in ApexCharts card templates.
- **Real-Time Control Switches (`binary_sensor` entities):**
  - `binary_sensor.nordpool_low` (`Running` / `ON`)
  - `binary_sensor.nordpool_high` (`Running` / `ON`)
  Provides instant triggers and conditions for standard Home Assistant automations.
- **Resource Efficient:** Performs in-memory updates only upon price updates or slider adjustments, preventing state memory bloat or recorder database database locks ($<16\text{KB}$ attribute limit compliance).

---

## 📦 Installation

### Option 1: Via HACS (Recommended)
1. Open **HACS** in your Home Assistant instance.
2. Click the three dots in the upper right corner $\rightarrow$ **Custom repositories**.
3. Add your repository URL: `https://github.com/YOUR_USERNAME/nordpool_smart_planner`
4. Select Category: **Integration** and click **Add**.
5. Find **Nordpool Smart Planner** in the list and click **Download**.
6. Restart Home Assistant.

### Option 2: Manual Installation
Copy the `custom_components/nordpool_smart_planner` directory into your Home Assistant `/config/custom_components/` directory and restart Home Assistant.

---

## ⚙️ Configuration

1. Go to **Settings** $\rightarrow$ **Devices & Services** $\rightarrow$ **Add Integration**.
2. Search for **Nordpool Smart Planner**.
3. Select your active Nordpool sensor entity (e.g., `sensor.nordpool_kwh_lv_eur_3_10_021`).
4. Once added, all 5 control sliders, 2 calculation sensors, and 2 binary relays will be created under the new device.

---

## 🤖 Automation Examples

### 1. Water Heater / Boiler (Low Cost Trigger)
```yaml
alias: "Boiler - Low Cost Power"
description: "Turn on water heater during cheap price windows"
trigger:
  - platform: state
    entity_id: binary_sensor.nordpool_low
    to: "on"
action:
  - service: switch.turn_on
    target:
      entity_id: switch.boiler_relay