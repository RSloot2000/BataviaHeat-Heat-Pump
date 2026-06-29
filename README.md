# BataviaHeat R290 - Home Assistant Integration

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://github.com/hacs/integration)

> **🚧 This project is in early development.** Expect breaking changes, incomplete features and undiscovered registers. Use at your own risk and please report any issues you encounter.

Custom Home Assistant integration for the **BataviaHeat R290 3–8 kW Monobloc** heat pump via DR164 gateway (Modbus TCP), ESP32 proxy (Modbus TCP) or RTU (Serial).

## Compatibility

The BataviaHeat R290 is manufactured by **Newntide** and sold under various brand names. This integration will likely work with other Newntide-based heat pumps that share the same Modbus register map, such as:

- BataviaHeat R290 3–8 kW (confirmed)
- Other Newntide OEM/white-label rebrands with identical controller hardware

If you have a Newntide-based heat pump from a different brand and can confirm compatibility, please [open an issue](https://github.com/RSloot2000/BataviaHeat-R290-Modbus/issues) so we can add it to the list. Or if you have the means, scan the registers yourself and help expand the project.

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

- **Climate entity:** heating on/off and target temperature control via pulse-coils
- **22 sensors:** temperatures, pressures, water pump data, operational status, thermal power, energy delivered
- **6 COP sensors:** built-in coefficient of performance tracking (current, today, week, month, year, all-time) — requires an external kWh meter entity
- **1 binary sensor:** compressor running
- **1 select entity:** power mode (standard / powerful / eco / auto)
- **3 switches:** unit power, silent mode, silent level 2 (pulse-coil based)
- **6 number entities:** heating curve (stooklijn) parameters and temperature limits
- **10-second polling interval** via Modbus TCP or RTU (Serial)
- **Triple connection support:** DR164 WiFi gateway (Modbus TCP), ESP32-S3 proxy (Modbus TCP) or Modbus RTU via USB RS-485 adapter
- **Optional register offload:** push raw registers to a NAS/HTTP endpoint for later decoding (disabled by default)
- **Connection failure resilience:** COP calculations remain accurate after network outages

## Hardware Requirements

| Component | Description |
|-----------|-------------|
| Heat pump | BataviaHeat R290 3–8 kW Monobloc |
| Modbus gateway (TCP) | DR164 RS485-to-WiFi converter (or any Modbus TCP gateway) |
| ESP32 proxy (TCP) | ESP32-S3 running the BataviaHeat Modbus-TCP proxy firmware |
| USB adapter (RTU) | Any USB RS-485 adapter (e.g. FTDI, CH340-based) |
| Wiring | Gateway / adapter connected to the heat pump's RS-485 port (A+ to A+, B− to B−) |

> **Choose one connection method:** DR164 gateway (Modbus TCP), ESP32 proxy (Modbus TCP) **or** Modbus RTU (direct USB serial connection to your Home Assistant host).

> **Important:** The RS-485 bus supports only one master. Disconnect the tablet controller from the bus before using this integration, or use the secondary RS-485 port located on the mainboard of the heatpump.

> **Note:** For a step-by-step guide on wiring the RS-485 to TCP adapter, see [RS-485 adapter installation](#rs-485-adapter-installation) below.

## Installation

### HACS (recommended)

1. Open **HACS** in Home Assistant
2. Click the three-dot menu → **Custom repositories**
3. Add `https://github.com/RSloot2000/BataviaHeat-R290-Modbus` and select **Integration**
4. Click **Download**
5. Restart Home Assistant

> **Stable vs beta:** HACS installs the latest tagged **release** by default. To test the newest changes, enable **Show beta versions** in the integration's download dialog — pre-release tags are served as beta. Stay on releases for everyday use.

### Manual

1. Copy the `custom_components/batavia_heat` folder into your Home Assistant `config/custom_components/` directory
2. Restart Home Assistant

## Configuration

1. Go to **Settings → Devices & Services → Add Integration**
2. Search for **BataviaHeat R290**
3. Select your connection type: **DR164 gateway (Modbus TCP)**, **ESP32 proxy (Modbus TCP)** or **Modbus RTU (Serial)**

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

### Options (kWh meter for COP)

After initial setup, you can optionally link an external kWh meter to enable COP sensors:

1. Go to **Settings → Devices & Services**
2. Find **BataviaHeat R290** and click **Configure**
3. Select your electricity meter entity (must have `device_class: energy`)
4. Save, the integration reloads automatically and creates six COP sensors

### Options (register offload)

Optionally push every register snapshot to a NAS/HTTP endpoint for later decoding (disabled by default):

1. Go to **Settings → Devices & Services** → **BataviaHeat R290** → **Configure**
2. Enable **Register offload** and enter an **Offload URL** (an HTTP endpoint that accepts a JSON POST)
3. Leave the URL empty to disable. Failures are logged and never interrupt normal updates

## Entities

### Sensors

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
| COP (current) | calculated | — | Real-time coefficient of performance¹ |
| COP (today) | calculated | — | Average COP for today¹ |
| COP (this week) | calculated | — | Average COP for the current week¹ |
| COP (this month) | calculated | — | Average COP for the current month¹ |
| COP (this year) | calculated | — | Average COP for the current year¹ |
| COP (all time) | calculated | — | Average COP since installation¹ |

> ¹ COP sensors are only created when an external kWh meter entity is configured in the integration options. See [COP calculation](#cop-calculation).

> HR[768], HR[773] and HR[776] go to 0 when the compressor is off. This is normal behaviour.

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

| Entity | Register | Options | Description |
|--------|----------|---------|-------------|
| Power mode | HR[6465] | Standard, Powerful, Eco, Auto | Operating power mode |

### Number entities

| Entity | Register | Range | Description |
|--------|----------|-------|-------------|
| Max heating temperature | HR[6402] | 0–85 °C | Maximum heating temperature |
| Heating curve mode | HR[6426] | 0–17 | Heating curve preset selector |
| Curve outdoor temp high | HR[6433] | −25–35 °C | Outdoor temperature at which minimum water temp applies |
| Curve outdoor temp low | HR[6434] | −25–35 °C | Outdoor temperature at which maximum water temp applies |
| Curve water temp mild | HR[6435] | 25–65 °C | Water temperature at mild outdoor conditions |
| Curve water temp cold | HR[6436] | 25–65 °C | Water temperature at cold outdoor conditions |

The heating curve registers use the M-register mapping: M00–M09 = HR[6400 + M], M10+ = HR[6400 + M + 15].

### Climate

| Entity | Description |
|--------|-------------|
| Heat Pump | HVAC modes: **Heat** / **Off**. Current temperature from HR[1350] (T80 total water outlet), target temperature from HR[772] (calculated heating curve setpoint, read-only). When the heating curve is off (M11 = 0), the target temperature can be adjusted via HR[6402] (M02). On/off via coils 1024/1025. |

## COP calculation

This integration has **built-in COP (Coefficient of Performance) sensors**. Thermal power and energy are calculated from Modbus data (flow rate × ΔT using HR[1348]/HR[1349] water temperatures). Electrical consumption is **not** available from the heat pump itself, it only reports compressor power, not total system consumption. An external kWh meter (e.g. HomeWizard) is required for COP calculation.

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

### Cannot connect
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

1. Use the [Modbus snooper tools](https://github.com/RSloot2000/BataviaHeat-R290-Modbus/tree/main/tools) to scan your heat pump
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
