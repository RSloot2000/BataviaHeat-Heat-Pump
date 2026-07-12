# BataviaHeat R290 — ESP32 Modbus Proxy Firmware

Firmware for an **ESP32-S3** that sits as a serializing man-in-the-middle between
the BataviaHeat tablet controller (Modbus-RTU master) and the heat pump (slave),
and exposes a **Modbus-TCP server on port 502** for Home Assistant. The
companion HACS integration connects to this proxy via the **ESP32 proxy** option.

## Hardware

- ESP32-S3-DevKitC-1
- 2× Waveshare TTL ↔ RS485 isolated adapters (auto-direction, no DE/RE)
- Fail-safe bypass relay (relay off = tablet directly on pump, heating keeps working)

| ESP32 | Adapter | Segment |
|-------|---------|---------|
| UART1 GPIO21 TX / GPIO47 RX | board #1 | Tablet |
| UART2 GPIO13 TX / GPIO14 RX | board #2 | Pump |
| GPIO10 | — | Fail-safe relay |

Log/upload over the onboard CH343 USB-UART (UART0).

## Build & flash

This is a [PlatformIO](https://platformio.org/) project.

1. Copy `include/secrets.h.example` to `include/secrets.h` and fill in your WiFi credentials.
2. Set `upload_port` in [platformio.ini](platformio.ini) to your ESP32's IP (OTA), or use the USB fallback.
3. Build & upload:
   - OTA: `pio run -t upload`
   - USB fallback: `pio run -e usb-flash -t upload`
   - RS485 loopback bench-test: `pio run -e rs485-loopback -t upload -t monitor`

## Configuration

Bus parameters, pins, cache age and sniffer logging live in [include/config.h](include/config.h).
The default slave ID is `1`, baud `9600` (8N1), TCP port `502`.

## Home Assistant

In the HACS integration choose **ESP32 proxy (Modbus TCP)** and enter the IP
address you assigned to this ESP32. Optional register offload is handled
Home-Assistant-side, so no firmware change is needed for it.

## Setup Example

Custom PCB with an ESP32 devkit, a step down converter (12V->5V) and 2 waveshare RS485 to TTL converters
![Custom PCB with an ESP32 devkit, a step down converter (12V->5V) and 2 waveshare RS485 to TTL converters](20260712_174357.jpg)