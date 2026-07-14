# BataviaHeat R290 - Home Assistant Integration

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://github.com/hacs/integration)
[![HACS validation](https://github.com/RSloot2000/BataviaHeat-Heat-Pump/actions/workflows/hacs.yml/badge.svg)](https://github.com/RSloot2000/BataviaHeat-Heat-Pump/actions/workflows/hacs.yml)
[![Hassfest](https://github.com/RSloot2000/BataviaHeat-Heat-Pump/actions/workflows/hassfest.yml/badge.svg)](https://github.com/RSloot2000/BataviaHeat-Heat-Pump/actions/workflows/hassfest.yml)
[![GitHub Release](https://img.shields.io/github/v/release/RSloot2000/BataviaHeat-Heat-Pump)](https://github.com/RSloot2000/BataviaHeat-Heat-Pump/releases)
[![GitHub Release Date](https://img.shields.io/github/release-date/RSloot2000/BataviaHeat-Heat-Pump)](https://github.com/RSloot2000/BataviaHeat-Heat-Pump/releases)
![Home Assistant](https://img.shields.io/badge/Home%20Assistant-2024.1.0%2B-blue?logo=home-assistant)
[![License](https://img.shields.io/github/license/RSloot2000/BataviaHeat-Heat-Pump)](https://github.com/RSloot2000/BataviaHeat-Heat-Pump/blob/main/LICENSE)
[![GitHub issues](https://img.shields.io/github/issues/RSloot2000/BataviaHeat-Heat-Pump)](https://github.com/RSloot2000/BataviaHeat-Heat-Pump/issues)
![Maintenance](https://img.shields.io/maintenance/yes/2026)

Custom Home Assistant integration for the **BataviaHeat R290 3–8 kW Monobloc** heat pump. Supports four connection types:

- **Cloud** — via your EcoHome app account (no extra hardware, works remotely)
- **DR164 gateway** — Modbus TCP via RS485-to-WiFi converter (local, fast)
- **ESP32 proxy** — Modbus TCP via ESP32-S3 proxy (local, fast)
- **Modbus RTU** — direct USB RS-485 serial connection

Cloud and a local Modbus connection can be combined: cloud acts as primary (setpoints, cloud-only sensors) and Modbus provides faster updates and deeper register access as backup/extension.

## Compatibility

The BataviaHeat R290 is manufactured by **Newntide** and sold under various brand names. This integration will likely work with other Newntide-based heat pumps that share the same Modbus register map, such as:

- BataviaHeat R290 3–8 kW (confirmed)
- Other Newntide OEM/white-label rebrands with identical controller hardware

If you have a Newntide-based heat pump from a different brand and can confirm compatibility, please [open an issue](https://github.com/RSloot2000/BataviaHeat-Heat-Pump/issues) so we can add it to the list. Or if you have the means, scan the registers yourself and help expand the project.

## Table of contents

- [Features](#features)
- [Compatibility](#compatibility)
- [Hardware Requirements](#hardware-requirements)
- [Installation](#installation)
- [Configuration](#configuration)
- [Entities](#entities)
  - [Sensors](#sensors)
  - [Binary sensors](#binary-sensors)
  - [Switches](#switches)
  - [Select entities](#select-entities)
  - [Number entities](#number-entities)
  - [Climate](#climate)
- [COP calculation](#cop-calculation)
- [Troubleshooting](#troubleshooting)
- [Documentation](#documentation)
- [Contributing](#contributing)
- [RS-485 adapter installation](#rs-485-adapter-installation)
- [License](#license)

Built by reverse-engineering the Modbus protocol using passive bus sniffing and systematic register scanning. The register map was validated over multiple overnight monitoring sessions totalling 850 000+ readings.

## Features

- **Climate entity:** on/off, heat/cool/auto modes, target temperature and power-mode preset
- **22 Modbus sensors:** temperatures, pressures, water pump data, operational status, thermal power, energy delivered
- **6 COP sensors:** built-in coefficient of performance tracking (current, today, week, month, year, all-time) — requires an external kWh meter entity
- **1 binary sensor:** compressor running
- **8 select entities:** power mode, auxiliary/external heat source mode, water pump operating & control type, lower-return pump sterilization/timed
- **3 switches:** unit power, silent mode, silent level 2 (pulse-coil based)
- **~20 number entities:** heating curve (stooklijn) parameters, temperature limits, auto-cool/holiday setpoints and water pump tuning
- **Cloud connection (EcoHome app account):**
  - 9 cloud-exclusive sensors: room temperature, compressor speed (rpm), hot water tank temperature, buffer top/bottom temperature, adjustable target temperature, solar boiler, underfloor heating inlet, pump fault info
  - Full cloud climate control: HVAC mode (cool/heat/auto) and on/off work in cloud-only mode via the device-detail endpoint
  - Hot water setpoint (writable, 18–75 °C)
  - Cloud select entities: silent mode, power mode, cooling/heating curves (zone A/B), light strip (writable remotely)
  - Cloud number entities: cooling setpoint, heating setpoint (zone A/B), light strip brightness
  - Thermal power and COP calculations use cloud data when Modbus is unavailable
- **Auto-hide:** sensors your unit does not have (e.g. DHW/solar/underfloor) hide themselves automatically and reappear if data returns
- **10-second polling** via Modbus TCP or RTU; **30-second polling** via cloud
- **Cloud + Modbus hybrid mode:** cloud is primary; Modbus provides faster updates and 40+ extra registers. Automatic fallback between the two
- **Optional register offload:** push raw registers to a NAS/HTTP endpoint or local path for later decoding (disabled by default)
- **Connection failure resilience:** COP calculations remain accurate after network outages

## Hardware Requirements

| Component | Description |
|-----------|-------------|
| Heat pump | BataviaHeat R290 3–8 kW Monobloc |
| Cloud account | EcoHome app account (no extra hardware required) |
| Modbus gateway (TCP) | DR164 RS485-to-WiFi converter (or any Modbus TCP gateway) |
| ESP32 proxy (TCP) | ESP32-S3 running the BataviaHeat Modbus-TCP proxy firmware |
| USB adapter (RTU) | Any USB RS-485 adapter (e.g. FTDI, CH340-based) |
| Wiring (Modbus only) | Gateway / adapter connected to the heat pump's RS-485 port (A+ to A+, B− to B−) |

> **Choose your primary connection:** Cloud (EcoHome account), DR164 gateway, ESP32 proxy, or Modbus RTU. Cloud and a local Modbus connection can be combined.

> **Important (Modbus only):** The RS-485 bus supports only one master. Disconnect the tablet controller from the bus before using this integration, or use the secondary RS-485 port located on the mainboard of the heat pump.

> **Note:** For a step-by-step guide on wiring the RS-485 to TCP adapter, see [RS-485 adapter installation](#rs-485-adapter-installation) below.

## Installation

### HACS (recommended)

1. Open **HACS** in Home Assistant
2. Click the three-dot menu → **Custom repositories**
3. Add `https://github.com/RSloot2000/BataviaHeat-Heat-Pump` and select **Integration**
4. Click **Download**
5. Restart Home Assistant

> **Stable vs beta:** HACS installs the latest tagged **release** by default. To test the newest changes, enable **Show beta versions** in the integration's download dialog — pre-release tags are served as beta. Stay on releases for everyday use.

### Manual

1. Copy the `custom_components/batavia_heat` folder into your Home Assistant `config/custom_components/` directory
2. Restart Home Assistant

## Configuration

1. Go to **Settings → Devices & Services → Add Integration**
2. Search for **BataviaHeat R290**
3. Select your primary connection type

### Cloud (EcoHome app account)

4. Enter your **EcoHome app credentials** (the same username and password as the app). Your password is stored as an MD5 hash, never in plaintext.
5. If multiple devices are on your account, select the correct one.
6. Optionally **add a local Modbus connection** as backup/extension:
   - Cloud remains primary (30 s polling)
   - When the cloud is unreachable, the integration falls back to Modbus automatically
   - Modbus adds 40+ extra registers (working mode, pump parameters, stooklijn, etc.) at 10 s polling
   - If you skip this step, the integration runs cloud-only

> **⚠ Single active session per account:** The EcoHome backend only allows **one active session per account**. Logging in here with your main account **logs you out of the EcoHome mobile app** (and logging back into the app logs Home Assistant out, triggering re-authentication). To avoid this tug-of-war, use a **separate EcoHome account** for Home Assistant and share the heat pump with it, so your phone app keeps its own session.

### DR164 gateway (Modbus TCP)

4. Enter the connection details:
   - **Host:** IP address of the DR164 gateway
   - **TCP port:** Gateway TCP port (default: `502`)
   - **Slave ID:** Modbus device address (default: `1`)

### ESP32 proxy (Modbus TCP)

4. Enter the connection details:
   - **Host:** IP address you assigned to the ESP32 proxy
   - **TCP port:** Proxy TCP port (default: `502`)
   - **Slave ID:** Modbus device address (default: `1`)

> No IP addresses are hardcoded — you supply the address of your own gateway/proxy during setup.

### Modbus RTU (Serial)

4. Enter the connection details:
   - **Serial port:** Device path (e.g. `/dev/ttyUSB0` on Linux, `COM3` on Windows)
   - **Slave ID:** Modbus device address (default: `1`)
   - **Baudrate:** Serial baudrate (default: `9600`, only change if needed)

### Options (connection details)

Modbus connection details can change over time (e.g. the DR164/ESP32 gets a new DHCP IP). You can update them **without removing the integration**:

1. Go to **Settings → Devices & Services** → **BataviaHeat R290** → **Configure**
2. For a TCP/ESP32 connection, edit **Host / IP address**, **TCP port** and **Slave ID**; for a serial connection, edit the **Serial port**, **Baudrate** and **Slave ID**
3. Save — the integration reloads and reconnects using the new details

> These fields only appear when a Modbus connection is configured (they are hidden for cloud-only setups).

### Options (kWh meter for COP)

After initial setup, you can optionally link an external kWh meter to enable COP sensors:

1. Go to **Settings → Devices & Services**
2. Find **BataviaHeat R290** and click **Configure**
3. Select your electricity meter entity (must have `device_class: energy`)
4. Save, the integration reloads automatically and creates six COP sensors

### Options (register offload)

Optionally push every register snapshot to a NAS/HTTP endpoint or local directory for later decoding (disabled by default):

1. Go to **Settings → Devices & Services** → **BataviaHeat R290** → **Configure**
2. Enable **Register offload** and enter an **Offload URL or local path**:
   - HTTP endpoint that accepts a JSON POST (e.g. `http://nas:8099/`), or
   - A local directory such as `/share/snooper` or `file:///share/snooper` (mount the NFS/CIFS share in **Settings → System → Storage** first; HA Core can only write to `/share`, `/media`, `/config`). Each poll writes a timestamped `snap_*.json`
3. Leave the field empty to disable. Failures are logged and never interrupt normal updates

## Entities

### Sensors

#### Modbus sensors

| Entity | Register | Unit | Description |
|--------|----------|------|-------------|
| Ambient temperature | IR[22] | °C | Outdoor temperature measured by the heat pump |
| Fin coil temperature | IR[23] | °C | Evaporator fin temperature |
| Suction temperature | IR[24] | °C | Compressor suction line temperature |
| Discharge temperature | IR[25] | °C | Compressor discharge line temperature |
| Low pressure | IR[32] | bar | Refrigerant low-side pressure |
| High pressure | IR[33] | bar | Refrigerant high-side pressure |
| Pump target speed | IR[53] | rpm | Water pump target speed |
| Pump flow rate | IR[54] | L/h | Water flow rate |
| Pump control signal | IR[66] | % | Pump PWM control signal |
| Pump feedback signal | IR[142] | % | Pump feedback signal |
| Condenser temperature | IR[135] | °C | Refrigerant-side condenser temperature (module 0#) |
| Module water outlet temperature | IR[137] | °C | Module water outlet |
| Module ambient temperature | IR[138] | °C | Module ambient |
| Operational status | HR[768] | - | Operating state (0 = off) |
| Heating target setpoint | HR[772] | °C | Calculated heating curve setpoint (read-only) |
| Compressor discharge temperature | HR[773] | °C | Compressor discharge (from outdoor unit) |
| Water outlet temperature | HR[776] | °C | System water outlet (from outdoor unit) |
| Plate HX water inlet temperature | HR[1348] | °C | Plate heat exchanger water inlet (T78) |
| Plate HX water outlet temperature | HR[1349] | °C | Plate heat exchanger water outlet (T79) |
| Total water outlet temperature | HR[1350] | °C | Total water outlet after plate HX (T80) |
| Buffer inlet temperature | HR[3230] | °C | Buffer tank inlet (water entering buffer) |
| Buffer outlet temperature | HR[3231] | °C | Buffer tank outlet (water leaving buffer) |
| Thermal power | calculated | kW | flow × ΔT × 4.186 / 3600 |
| Energy delivered | integrated | kWh | Riemann sum of thermal power |
| Cooling power | calculated | kW | Cooling magnitude (positive while cooling, 0 while heating) |
| Cooling energy delivered | integrated | kWh | Riemann sum of cooling power |
| COP (current) | calculated | — | Real-time coefficient of performance (heating)¹ |
| COP (today) | calculated | — | Average COP for today¹ |
| COP (this week) | calculated | — | Average COP for the current week¹ |
| COP (this month) | calculated | — | Average COP for the current month¹ |
| COP (this year) | calculated | — | Average COP for the current year¹ |
| COP (all time) | calculated | — | Average COP since installation¹ |
| EER (current/today/week/month/year/all time) | calculated | — | Cooling efficiency, same periods as COP¹ |

> ¹ COP sensors are only created when an external kWh meter entity is configured in the integration options. See [COP calculation](#cop-calculation).

> HR[768], HR[773] and HR[776] go to 0 when the compressor is off. This is normal behaviour.

#### Cloud sensors (only when cloud connection is configured)

| Entity | Cloud address | Unit | Description |
|--------|--------------|------|-------------|
| Room temperature | 2097 | °C | Room/water temperature as reported by the cloud |
| Compressor speed | 2072 | rpm | Live compressor speed |
| Hot water tank temperature | 2100 | °C | DHW storage tank temperature |
| Buffer top temperature | 2104 | °C | Upper buffer tank sensor |
| Buffer bottom temperature | 2105 | °C | Lower buffer tank sensor |
| Adjustable target temperature | 2011 | °C | Current adjustable target temperature |
| Solar boiler temperature | 2103 | °C | Solar boiler sensor (hidden when not present) |
| Underfloor heating inlet temperature | 2111 | °C | Underfloor loop water inlet (hidden when not present) |
| Pump fault info | 2195 | — | Inverter water-pump fault code (0 = OK) |

When cloud is configured **without** a Modbus backup, the following additional cloud sensors are also created (they duplicate Modbus sensors but use cloud data):

| Entity | Cloud address | Modbus equivalent |
|--------|--------------|-------------------|
| Outdoor temperature (cloud) | 2099 | IR[22] |
| Plate HX inlet (cloud) | 2187 | HR[1348] |
| Plate HX outlet (cloud) | 2188 | HR[1349] |
| Total water outlet (cloud) | 2189 | HR[1350] |
| HP water outlet (cloud) | 2106 | HR[776] |
| Fin coil temperature (cloud) | 2142 | IR[23] |
| Discharge temperature (cloud) | 2143 | IR[25] |
| Suction temperature (cloud) | 2144 | IR[24] |
| Low pressure (cloud) | 2149 | IR[32] |
| High pressure (cloud) | 2150 | IR[33] |
| Pump target speed (cloud) | 2191 | IR[53] |
| Pump flow rate (cloud) | 2192 | IR[54] |
| Pump control signal (cloud) | 2193 | IR[66] |
| Pump feedback signal (cloud) | 2194 | IR[142] |

### Binary sensors

| Entity | Register | Description |
|--------|----------|-------------|
| Compressor running | HR[1283] | Whether the compressor is currently active |

### Switches

| Entity | ON coil | OFF coil | Description |
|--------|---------|----------|-------------|
| Unit power | 1024 | 1025 | Turn the heat pump on or off |
| Silent mode | 1073 | 1074 | Enable or disable silent mode |
| Silent level 2 | 1076 | 1075 | Switch between silent level 1 and 2 |

Switches use **pulse-coils** (FC05, 0xFF00). Each function has a separate ON and OFF coil; there is no toggle. Coil state is not readable; the UI uses assumed state.

### Select entities

#### Modbus select entities

| Entity | Register | Options | Description |
|--------|----------|---------|-------------|
| Power mode | HR[6465] | Standard, Powerful, Eco, Auto | N01 operating power mode |
| Auxiliary heater mode | HR[7189] | Off, Heating only, DHW only, Heating+DHW | M39 auxiliary electric heater |
| External heat source mode | HR[7190] | Off, Heating only, DHW only, Heating+DHW | M40 external heat source |
| Pump operating mode | HR[6472] | Continuous, Stop at temp, Intermittent | P01 water pump mode |
| Pump control type | HR[7232] | Speed, Flow, On-Off, Power | P02 pump control type |
| Lower return pump sterilization | HR[7238] | Off, On | P07 |
| Lower return pump timed | HR[7239] | Off, On | P08 |

#### Cloud select entities (only when cloud connection is configured)

| Entity | Cloud address | Options | Description |
|--------|--------------|---------|-------------|
| Silent mode (cloud) | 1004 | Off, On | Enables/disables silent mode via cloud |
| Power mode (cloud) | 1031 | Standard, Powerful, Eco, Auto | Power mode via cloud |
| Cooling curve zone A (cloud) | 1046 | Off / Low temp 1–8 / High temp 1–8 / 2P / SOT | Cooling climate curve, zone A |
| Heating curve zone A (cloud) | 1047 | Off / Low temp 1–8 / High temp 1–8 / 2P / SOT | Heating climate curve, zone A |
| Heating curve zone B (cloud) | 1049 | Off / Low temp 1–8 / High temp 1–8 / 2P / SOT | Heating climate curve, zone B |
| Light strip (cloud) | 4111 | Off, On | Display light strip (hidden when not present) |

Cloud selects are always shown when cloud is configured. When Modbus is also configured, the local Modbus variants are preferred for reading; cloud selects provide a remote-write path independent of local connectivity.

### Number entities

#### Modbus number entities

| Entity | Register | Range | Description |
|--------|----------|-------|-------------|
| Max heating temperature | HR[6402] | 0–85 °C | Maximum heating temperature |
| Heating curve mode | HR[6426] | 0–17 | Heating curve preset selector |
| Curve outdoor temp high | HR[6433] | −25–35 °C | Outdoor temperature at which minimum water temp applies |
| Curve outdoor temp low | HR[6434] | −25–35 °C | Outdoor temperature at which maximum water temp applies |
| Curve water temp mild | HR[6435] | 25–65 °C | Water temperature at mild outdoor conditions |
| Curve water temp cold | HR[6436] | 25–65 °C | Water temperature at cold outdoor conditions |
| Auto-cool min ambient | HR[7184] | 20–29 °C | M35 min outdoor temp for auto cooling |
| Auto-cool max ambient | HR[7185] | 10–17 °C | M36 max outdoor temp for auto cooling |
| Holiday heating temperature | HR[7186] | 20–25 °C | M37 holiday-away heating |
| Holiday DHW temperature | HR[7187] | 20–25 °C | M38 holiday-away DHW |
| Pump target speed setpoint | HR[7234] | 1000–6800 rpm | P03 pump target speed |
| Pump manufacturer | HR[7235] | 0–8 | P04 pump manufacturer code |
| Pump target flow setpoint | HR[7236] | 0–3600 L/h | P05 pump target flow |
| Lower return pump interval | HR[7237] | 5–120 min | P06 lower-return pump interval |
| Pump intermittent stop time | HR[6507] | min | P09 |
| Pump intermittent run time | HR[6511] | min | P20 |

#### Cloud number entities (only when cloud connection is configured)

| Entity | Cloud address | Range | Description |
|--------|--------------|-------|-------------|
| Hot water setpoint | 1024 | 18–75 °C | DHW target temperature (always shown) |
| Cooling setpoint (cloud) | 1022 | 10–35 °C | Cooling target (shown when Modbus not configured) |
| Heating setpoint (cloud) | 1023 | 20–80 °C | Heating target via cloud (shown when Modbus not configured) |
| Heating setpoint zone B (cloud) | 1029 | 20–70 °C | Zone B heating target (shown when Modbus not configured) |
| Light strip brightness (cloud) | 4112 | 10–100 % | Display light strip brightness (hidden when not present) |

The hot water setpoint (cloud address 1024) is always available via cloud — there is no direct Modbus equivalent in the current register map.

The heating curve registers use the M-register mapping: M00–M09 = HR[6400 + M], M10+ = HR[6400 + M + 15]. M35–M40 and most P-series live in a separate HR[7184–] / HR[7232–] block (sniffer-confirmed).

### Climate

| Entity | Description |
|--------|-------------|
| Heat Pump | HVAC modes: **Off** / **Heat** / **Cool** / **Auto**, plus power-mode presets (standard/powerful/eco/auto). Current temperature from HR[1350] (T80 total water outlet), with fallback to cloud addresses 2189/2106 when Modbus is unavailable. Target temperature from HR[772] (calculated heating curve setpoint), with fallback to cloud address 1023. When the heating curve is off (M11 = 0), the target temperature can be adjusted via HR[6402] (M02). Working mode via HR[6400]; on/off via coils 1024/1025. |

> **Cloud-only mode:** when no Modbus connection is configured, the climate entity is fully functional using the EcoHome cloud. Current and target temperature, **HVAC mode (cool/heat/auto)** and **on/off** are all available — mode is written via cloud address 1021 and power via 1017 (device-detail endpoint). The target temperature follows the active mode (cooling setpoint 1022 / heating setpoint 1023) and, as on the tablet, becomes read-only while a climate curve is active.

## COP calculation

This integration has **built-in COP (Coefficient of Performance) sensors**. Thermal power is calculated from flow rate × ΔT using plate HX water temperatures. The calculation uses **Modbus data first** (IR[54] flow, HR[1348]/HR[1349] temperatures) and **falls back to cloud data** (cloud addresses 2192/2187/2188) when Modbus is unavailable. This means COP tracking works in cloud-only mode too, as long as those cloud sensors are reporting values.

**Heating vs cooling are tracked separately.** In heating the water is warmed (outlet > inlet) → **COP** sensors. In cooling the water is chilled (outlet < inlet) → separate **cooling power**, **cooling energy delivered** and **EER** sensors. Each mode only accumulates while it is actually running, so the metrics don't blend.

Electrical consumption is **not** available from the heat pump itself. An external kWh meter (e.g. HomeWizard) is required for COP calculation.

### Setup

1. Go to **Settings → Devices & Services**
2. Find the **BataviaHeat R290** integration and click **Configure**
3. Select your electricity meter entity (must have `device_class: energy`)
4. Save — six COP sensors will be created automatically

### COP sensors

| Sensor | Description |
|--------|-------------|
| COP (current) | Real-time COP based on instantaneous thermal and electrical power |
| COP (today) | Average COP for today |
| COP (this week) | Average COP for the current week |
| COP (this month) | Average COP for the current month |
| COP (this year) | Average COP for the current year |
| COP (all time) | Average COP since installation |

Period sensors are **install-date aware**: if the integration is installed mid-month, the first month's COP only counts from the installation date onwards.

### Connection failure resilience

Both thermal and electrical energy are accumulated using the same time-gap guard. If the connection drops for more than one hour, both sides pause simultaneously. This prevents skewed COP values after network outages, the ratio stays correct because neither side accumulates energy during the gap.

> **No kWh meter?** Leave the options field empty. The integration works without COP sensors; you can always configure the meter later.

## Troubleshooting

### Cannot connect (cloud)
- Verify your EcoHome app credentials are correct
- Check that the device appears online in the EcoHome app
- If the device is shared with you by an installer, it will be discovered automatically via the shared-devices endpoint
- After 3 consecutive cloud failures the integration falls back to Modbus (if configured) and retries cloud on every subsequent cycle

### Cannot connect (Modbus TCP)
- Verify the Modbus TCP gateway is powered on and connected to your network
- Check that the IP address is correct and reachable from your Home Assistant instance
- Confirm the TCP port (default 502) and slave ID (default 1)
- Check RS-485 wiring

### Cannot connect (serial)
- Verify the USB RS-485 adapter is plugged in and detected by the OS
- Check the serial port path (run `ls /dev/ttyUSB*` or `ls /dev/ttyACM*` on Linux)
- On Home Assistant OS, the device may appear as `/dev/ttyUSB0` or `/dev/ttyACM0`
- Make sure your Home Assistant user has permissions to access the serial port

### Entities unavailable
- Check Home Assistant logs for Modbus communication errors
- Make sure the **tablet controller is disconnected** from the RS-485 bus if you are using this bus. Two masters on the same bus cause conflicts
- If readings are intermittent, try increasing the scan interval

### Sensors show 0
- HR[768], HR[773] and HR[776] return 0 when the compressor is off; this is expected
- If input register sensors show 0, verify your gateway connection is stable

## Documentation

The [`docs/`](docs/) folder contains reference documentation for the BataviaHeat R290:

- **[tablet-parameters.md](docs/tablet-parameters.md)** (NL) — Complete list of all installer parameters (N/M/F/P/G series) with HR-addresses, ranges, default values, error codes (E/F series), and optimization tips
- **[tablet-parameters-en.md](docs/tablet-parameters-en.md)** (EN) — Same content in English

## Contributing

This integration was built by reverse-engineering the Modbus protocol. Contributions are welcome:

1. Use the [Modbus snooper tools](https://github.com/RSloot2000/BataviaHeat-Heat-Pump/tree/main/tools) to scan your heat pump
2. Share discovered register definitions
3. Report issues with register values or entity behaviour
4. Suggest new features or improvements

## RS-485 adapter installation

### Wiring

The heat pump's RS-485 connector uses a 4-wire cable with the following colour coding:

| Wire colour | Function |
|-------------|----------|
| 🔴 Red | 12 V |
| ⚫ Black | GND (bus + DC) |
| ⚪ White | A |
| 🟢 Green | B |

Connect **White (A)** to the **A+** terminal and **Green (B)** to the **B−** terminal on your RS-485 gateway or USB adapter. The red and black wires carry 12 V DC power and are **not** needed for the Modbus data connection.

## License

MIT
