"""Constants for the BataviaHeat R290 integration."""

DOMAIN = "batavia_heat"
MANUFACTURER = "BataviaHeat"
MODEL = "R290 3-8kW Monobloc"

# === Connection defaults ===
DEFAULT_TCP_PORT = 502
DEFAULT_SLAVE_ID = 1
DEFAULT_BAUDRATE = 9600

CONF_HOST = "host"
CONF_TCP_PORT = "tcp_port"
CONF_SLAVE_ID = "slave_id"
CONF_CONNECTION_TYPE = "connection_type"
CONF_SERIAL_PORT = "serial_port"
CONF_BAUDRATE = "baudrate"
CONF_ENERGY_ENTITY = "energy_entity"

CONNECTION_TCP = "tcp"          # DR164 RS485-WiFi gateway (tablet bus-sharing)
CONNECTION_SERIAL = "serial"    # Direct USB/RS485 dongle
CONNECTION_ESP32 = "esp32"      # ESP32-S3 Modbus-TCP proxy (own bus, no tablet)
CONNECTION_CLOUD = "cloud"      # EcoHome cloud API (primary), optional Modbus backup

# === Cloud connection config keys ===
CONF_CLOUD_USERNAME = "cloud_username"
CONF_CLOUD_PASSWORD_HASH = "cloud_password_hash"   # MD5 hex digest (never plaintext)
CONF_CLOUD_DEVICE_CODE = "cloud_device_code"
CONF_CLOUD_DEVICE_NAME = "cloud_device_name"
# Set to True when Modbus is added as a backup/extension alongside cloud.
CONF_MODBUS_ENABLED = "modbus_enabled"
# Modbus connection type when used as cloud backup (tcp / serial / esp32).
CONF_MODBUS_CONNECTION_TYPE = "modbus_connection_type"

# Polling interval for the cloud path (seconds).
DEFAULT_CLOUD_SCAN_INTERVAL = 30
# Consecutive cloud failures before falling back to Modbus-only.
CLOUD_FAILURE_THRESHOLD = 3

# === Optional register offload (push raw registers to NAS for later decode) ===
CONF_OFFLOAD_ENABLED = "offload_enabled"
CONF_OFFLOAD_URL = "offload_url"  # HTTP endpoint, blank = disabled
# Max size of the consolidated snapshots.db in MB. When exceeded, the oldest
# snapshots are pruned on each append until the file fits again. 0 = no limit.
CONF_OFFLOAD_DB_MAX_MB = "offload_db_max_mb"
DEFAULT_OFFLOAD_DB_MAX_MB = 0

# Update interval in seconds (10s is comfortable for DR164 gateway latency)
DEFAULT_SCAN_INTERVAL = 10

# Special marker values for disconnected sensors
SENSOR_DISCONNECTED = (32834, 32836)  # 0x8042, 0x8044 → -3270.x°C

# === Register definitions ===
# Discovered via Modbus scanner on 2026-03-15, cross-referenced with EcoHome App.
# Validated with 9-hour overnight combined active+passive monitoring (2026-03-15/16).
# Further validated with 9.4-hour targeted monitoring (2026-03-16/17):
#   851,978 readings, 388 distinct holding + 41 input register addresses.
#
# entity_type: "sensor" = read-only sensor, "number" = writable setpoint,
#              "select" = writable enum, "switch" = writable boolean
#
# IMPORTANT: Overnight monitoring revealed that holding register "sensor" values
# (HR[5,72,74-76,187-189]) are NOT maintained by the heat pump itself. They showed
# 0 or inconsistent values all night. These values are likely written by the
# controller tablet when its app is active. Only Input Registers contain reliable
# real-time sensor data from the heat pump hardware.
#
# HR[768], HR[773], HR[776], HR[1338] are from the operational/compressor block.
# These registers go to 0 when the compressor is off — this is expected behavior.

# ── Holding registers (read/write) - FC03/FC06 ──
HOLDING_REGISTERS: dict[int, dict] = {
    # NOTE: HR[4] was originally mapped as "heating_target_temperature" but reads 0
    # in practice. The actual setpoint used by the system is HR[6402] (M02 parameter).
    #
    # NOTE: Holding register sensors (HR[5,72,74-76,187-189]) were removed after
    # overnight monitoring proved they are NOT maintained by the heat pump.
    # They showed 0 or nonsensical values throughout 9 hours of monitoring.
    # Real sensor data is available only via Input Registers (FC04).

    # ─── Operational Status & Live Sensors (from outdoor unit) ───
    # These go to 0 when compressor is off. This is normal behavior.
    768: {
        "name": "operational_status",
        "device_class": None,
        "unit": None,
        "scale": 1,
        "entity_type": "sensor",
        "icon": "mdi:heat-pump-outline",
    },
    # ─── Status mirrors (persistent state the tablet reads back) ───
    # HR[912] = unit power state (0=off, 1=on); HR[913] = silent-mode bitfield
    # (0=off, 1=L1, 3=L2). Pulse-coils are write-only; these mirror the state.
    912: {
        "name": "unit_power_state",
        "device_class": None,
        "unit": None,
        "scale": 1,
        "entity_type": "binary_sensor",
        "icon": "mdi:power",
    },
    913: {
        "name": "silent_mode_state",
        "device_class": None,
        "unit": None,
        "scale": 1,
        "entity_type": "sensor",
        "icon": "mdi:volume-off",
    },
    772: {
        "name": "heating_target_setpoint",
        "device_class": "temperature",
        "unit": "°C",
        "scale": 0.1,
        "entity_type": "sensor",
        "icon": "mdi:thermostat",
    },
    773: {
        "name": "compressor_discharge_temperature",
        "device_class": "temperature",
        "unit": "°C",
        "scale": 0.1,
        "entity_type": "sensor",
    },
    776: {
        "name": "water_outlet_temperature",
        "device_class": "temperature",
        "unit": "°C",
        "scale": 0.1,
        "entity_type": "sensor",
    },
    # ─── Plate Heat Exchanger Water Temperatures ───
    # Discovered 2026-04-14: T78/T79 from tablet module status map to HR[1348]/HR[1349].
    # Previously mis-mapped to IR[135]/IR[136] which are refrigerant-side temps.
    1348: {
        "name": "plate_hx_water_inlet_temperature",
        "device_class": "temperature",
        "unit": "°C",
        "scale": 0.1,
        "entity_type": "sensor",
    },
    1349: {
        "name": "plate_hx_water_outlet_temperature",
        "device_class": "temperature",
        "unit": "°C",
        "scale": 0.1,
        "entity_type": "sensor",
    },
    1350: {
        "name": "total_water_outlet_temperature",
        "device_class": "temperature",
        "unit": "°C",
        "scale": 0.1,
        "entity_type": "sensor",
    },

    # ─── Buffer Tank Temperatures ───
    # Discovered 2026-04-14: buffer inlet/outlet from tablet match HR[3230]/HR[3231].
    3230: {
        "name": "buffer_inlet_temperature",
        "device_class": "temperature",
        "unit": "°C",
        "scale": 0.1,
        "entity_type": "sensor",
    },
    3231: {
        "name": "buffer_outlet_temperature",
        "device_class": "temperature",
        "unit": "°C",
        "scale": 0.1,
        "entity_type": "sensor",
    },

    # ─── Energy & Power Monitoring ───
    # HR[41] (compressor_power), HR[1325] (inverter_current), HR[1338] (mains_voltage),
    # HR[1368] (dc_bus_voltage) removed — HomeWizard kWh meter replaces these.
    1283: {
        "name": "compressor_running",
        "device_class": None,
        "unit": None,
        "scale": 1,
        "entity_type": "binary_sensor",
        "icon": "mdi:heat-pump",
    },

    # ─── N-serie: System Configuration ───
    6400: {
        "name": "working_mode",
        "device_class": None,
        "unit": None,
        "scale": 1,
        "entity_type": "select",
        "icon": "mdi:sun-snowflake-variant",
        "options": {
            1: "cool",
            2: "heat",
            3: "auto",
        },
    },
    6465: {
        "name": "power_mode",
        "device_class": None,
        "unit": None,
        "scale": 1,
        "entity_type": "select",
        "icon": "mdi:lightning-bolt",
        "options": {
            0: "standard",
            1: "powerful",
            2: "eco",
            3: "auto",
        },
    },

    # ─── Heating Curve Parameters (M-registers) ───
    # Non-linear HR mapping: M00-M09 = HR[6400+Mxx], M10-M21 = HR[6400+Mxx+15],
    # M35-M40 = HR[7184-7190] (gap at 7188). All sniffer-confirmed.
    6401: {
        "name": "cooling_setpoint_temperature",
        "device_class": "temperature",
        "unit": "°C",
        "scale": 1,
        "min": 15,
        "max": 35,
        "entity_type": "number",
        "icon": "mdi:snowflake-thermometer",
    },
    6402: {
        "name": "max_heating_temperature",
        "device_class": "temperature",
        "unit": "°C",
        "scale": 1,
        "min": 0,
        "max": 85,
        "entity_type": "number",
        "icon": "mdi:thermometer-chevron-up",
    },
    6404: {
        "name": "cooling_target_room_temperature",
        "device_class": "temperature",
        "unit": "°C",
        "scale": 1,
        "min": 0,
        "max": 80,
        "entity_type": "number",
        "icon": "mdi:home-thermometer",
    },
    6405: {
        "name": "heating_target_room_temperature",
        "device_class": "temperature",
        "unit": "°C",
        "scale": 1,
        "min": 0,
        "max": 80,
        "entity_type": "number",
        "icon": "mdi:home-thermometer",
    },
    6408: {
        "name": "heating_setpoint_zone_b",
        "device_class": "temperature",
        "unit": "°C",
        "scale": 1,
        "min": 40,
        "max": 60,
        "entity_type": "number",
        "icon": "mdi:thermometer-chevron-up",
    },
    6425: {
        "name": "cooling_curve_zone_a",
        "device_class": None,
        "unit": None,
        "scale": 1,
        "min": 0,
        "max": 17,
        "entity_type": "number",
        "icon": "mdi:chart-line",
    },
    6426: {
        "name": "heating_curve_mode",
        "device_class": None,
        "unit": None,
        "scale": 1,
        "min": 0,
        "max": 17,
        "entity_type": "number",
        "icon": "mdi:chart-line",
    },
    6427: {
        "name": "cooling_curve_zone_b",
        "device_class": None,
        "unit": None,
        "scale": 1,
        "min": 0,
        "max": 17,
        "entity_type": "number",
        "icon": "mdi:chart-line",
    },
    6428: {
        "name": "heating_curve_zone_b",
        "device_class": None,
        "unit": None,
        "scale": 1,
        "min": 0,
        "max": 17,
        "entity_type": "number",
        "icon": "mdi:chart-line",
    },
    6429: {
        "name": "cool_custom_outdoor_temp_1",
        "device_class": "temperature",
        "unit": "°C",
        "scale": 1,
        "min": -5,
        "max": 46,
        "entity_type": "number",
        "icon": "mdi:snowflake-thermometer",
    },
    6430: {
        "name": "cool_custom_outdoor_temp_2",
        "device_class": "temperature",
        "unit": "°C",
        "scale": 1,
        "min": -5,
        "max": 46,
        "entity_type": "number",
        "icon": "mdi:snowflake-thermometer",
    },
    6431: {
        "name": "cool_custom_outlet_temp_1",
        "device_class": "temperature",
        "unit": "°C",
        "scale": 1,
        "min": 5,
        "max": 25,
        "entity_type": "number",
        "icon": "mdi:thermometer-water",
    },
    6432: {
        "name": "cool_custom_outlet_temp_2",
        "device_class": "temperature",
        "unit": "°C",
        "scale": 1,
        "min": 5,
        "max": 25,
        "entity_type": "number",
        "icon": "mdi:thermometer-water",
    },
    6433: {
        "name": "curve_outdoor_temp_high",
        "device_class": "temperature",
        "unit": "°C",
        "scale": 1,
        "min": -25,
        "max": 35,
        "entity_type": "number",
        "icon": "mdi:thermometer-plus",
    },
    6434: {
        "name": "curve_outdoor_temp_low",
        "device_class": "temperature",
        "unit": "°C",
        "scale": 1,
        "min": -25,
        "max": 35,
        "entity_type": "number",
        "icon": "mdi:thermometer-minus",
    },
    6435: {
        "name": "curve_water_temp_mild",
        "device_class": "temperature",
        "unit": "°C",
        "scale": 1,
        "min": 25,
        "max": 65,
        "entity_type": "number",
        "icon": "mdi:thermometer-water",
    },
    6436: {
        "name": "curve_water_temp_cold",
        "device_class": "temperature",
        "unit": "°C",
        "scale": 1,
        "min": 25,
        "max": 65,
        "entity_type": "number",
        "icon": "mdi:thermometer-water",
    },
    # ─── Auto-cool / holiday / heat-source block HR[7184-7190] (M35-M40) ───
    # Sniffer-confirmed 2026-06-29. NOT at 6440/6450 as previously guessed.
    7184: {
        "name": "auto_cool_min_ambient",
        "device_class": "temperature",
        "unit": "°C",
        "scale": 1,
        "min": 20,
        "max": 29,
        "entity_type": "number",
        "icon": "mdi:snowflake-thermometer",
    },
    7185: {
        "name": "auto_cool_max_ambient",
        "device_class": "temperature",
        "unit": "°C",
        "scale": 1,
        "min": 10,
        "max": 17,
        "entity_type": "number",
        "icon": "mdi:snowflake-thermometer",
    },
    7186: {
        "name": "holiday_heating_temperature",
        "device_class": "temperature",
        "unit": "°C",
        "scale": 1,
        "min": 20,
        "max": 25,
        "entity_type": "number",
        "icon": "mdi:beach",
    },
    7187: {
        "name": "holiday_dhw_temperature",
        "device_class": "temperature",
        "unit": "°C",
        "scale": 1,
        "min": 20,
        "max": 25,
        "entity_type": "number",
        "icon": "mdi:beach",
    },
    7189: {
        "name": "auxiliary_heater_mode",
        "device_class": None,
        "unit": None,
        "scale": 1,
        "entity_type": "select",
        "icon": "mdi:radiator",
        "options": {
            0: "off",
            1: "heating_only",
            2: "dhw_only",
            3: "heating_and_dhw",
        },
    },
    7190: {
        "name": "external_heat_source_mode",
        "device_class": None,
        "unit": None,
        "scale": 1,
        "entity_type": "select",
        "icon": "mdi:fire-circle",
        "options": {
            0: "off",
            1: "heating_only",
            2: "dhw_only",
            3: "heating_and_dhw",
        },
    },

    # ─── P-serie: Water Pump (sniffer-confirmed 2026-06-29) ───
    # P01=6472, P02-P08=7232-7239 (gap 7233), P09=6507, P20=6511.
    6472: {
        "name": "pump_operating_mode",
        "device_class": None,
        "unit": None,
        "scale": 1,
        "entity_type": "select",
        "icon": "mdi:pump",
        "options": {
            0: "continuous",
            1: "stop_at_temp",
            2: "intermittent",
        },
    },
    7232: {
        "name": "pump_control_type",
        "device_class": None,
        "unit": None,
        "scale": 1,
        "entity_type": "select",
        "icon": "mdi:pump",
        "options": {
            1: "speed",
            2: "flow",
            3: "on_off",
            4: "power",
        },
    },
    7234: {
        "name": "pump_target_speed_setpoint",
        "device_class": None,
        "unit": "rpm",
        "scale": 1,
        "min": 1000,
        "max": 6800,
        "entity_type": "number",
        "icon": "mdi:pump",
    },
    7235: {
        "name": "pump_manufacturer",
        "device_class": None,
        "unit": None,
        "scale": 1,
        "min": 0,
        "max": 8,
        "entity_type": "number",
        "icon": "mdi:factory",
    },
    7236: {
        "name": "pump_target_flow_setpoint",
        "device_class": None,
        "unit": "L/h",
        "scale": 1,
        "min": 0,
        "max": 3600,
        "entity_type": "number",
        "icon": "mdi:water-pump",
    },
    7237: {
        "name": "lower_return_pump_interval",
        "device_class": None,
        "unit": "min",
        "scale": 1,
        "min": 5,
        "max": 120,
        "entity_type": "number",
        "icon": "mdi:timer-outline",
    },
    7238: {
        "name": "lower_return_pump_sterilization",
        "device_class": None,
        "unit": None,
        "scale": 1,
        "entity_type": "select",
        "icon": "mdi:water-pump",
        "options": {
            0: "off",
            1: "on",
        },
    },
    7239: {
        "name": "lower_return_pump_timed",
        "device_class": None,
        "unit": None,
        "scale": 1,
        "entity_type": "select",
        "icon": "mdi:water-pump",
        "options": {
            0: "off",
            1: "on",
        },
    },
    6507: {
        "name": "pump_intermittent_stop_time",
        "device_class": None,
        "unit": "min",
        "scale": 1,
        "min": 0,
        "max": 999,
        "entity_type": "number",
        "icon": "mdi:timer-pause-outline",
    },
    6511: {
        "name": "pump_intermittent_run_time",
        "device_class": None,
        "unit": "min",
        "scale": 1,
        "min": 0,
        "max": 999,
        "entity_type": "number",
        "icon": "mdi:timer-play-outline",
    },
}

# ── Calculated sensors (derived from multiple registers) ──
# These don't have a Modbus address — they're computed in sensor.py.
#
# NOTE: HR[163-165] are 16-bit Wh counters that overflow every ~65.5 kWh (~12 days
# at optimized settings). Too unreliable as primary energy source.
# Instead, use HA's Riemann Sum Integration helper on compressor_power (HR[41])
# for accurate kWh tracking with zero data loss.
#
# For delivered thermal energy (kWh), use Riemann Sum Integration on thermal_power.
CALCULATED_SENSORS: dict[str, dict] = {
    "thermal_power": {
        "name": "thermal_power",
        "device_class": "power",
        "unit": "kW",
        "icon": "mdi:fire",
        "description": "Calculated: flow_rate × (outlet − inlet) × 4.186 / 3600",
        # Sources: IR[54] flow L/h, HR[1348] inlet °C (T78), HR[1349] outlet °C (T79)
    },
    "cooling_power": {
        "name": "cooling_power",
        "device_class": "power",
        "unit": "kW",
        "icon": "mdi:snowflake",
        "description": "Calculated: flow_rate × (inlet − outlet) × 4.186 / 3600 (cooling)",
        # Cooling magnitude: positive while cooling (outlet < inlet), 0 while heating.
    },
}

# ── Input registers (read-only) - FC04 ──
INPUT_REGISTERS: dict[int, dict] = {
    # ─── Refrigerant Temperatures ───
    22: {
        "name": "ambient_temperature",
        "device_class": "temperature",
        "unit": "°C",
        "scale": 0.1,
        "entity_type": "sensor",
    },
    23: {
        "name": "fin_coil_temperature",
        "device_class": "temperature",
        "unit": "°C",
        "scale": 0.1,
        "entity_type": "sensor",
    },
    24: {
        "name": "suction_temperature",
        "device_class": "temperature",
        "unit": "°C",
        "scale": 0.1,
        "entity_type": "sensor",
    },
    25: {
        "name": "discharge_temperature",
        "device_class": "temperature",
        "unit": "°C",
        "scale": 0.1,
        "entity_type": "sensor",
    },

    # ─── Pressures ───
    32: {
        "name": "low_pressure",
        "device_class": "pressure",
        "unit": "bar",
        "scale": 0.1,
        "entity_type": "sensor",
    },
    33: {
        "name": "high_pressure",
        "device_class": "pressure",
        "unit": "bar",
        "scale": 0.1,
        "entity_type": "sensor",
    },

    # ─── Water Circuit / Pump ───
    53: {
        "name": "pump_target_speed",
        "device_class": None,
        "unit": "rpm",
        "scale": 1,
        "entity_type": "sensor",
        "icon": "mdi:pump",
    },
    54: {
        "name": "pump_flow_rate",
        "device_class": None,
        "unit": "L/h",
        "scale": 1,
        "entity_type": "sensor",
        "icon": "mdi:water-pump",
    },
    66: {
        "name": "pump_control_signal",
        "device_class": None,
        "unit": "%",
        "scale": 0.1,
        "entity_type": "sensor",
        "icon": "mdi:pump",
    },
    142: {
        "name": "pump_feedback_signal",
        "device_class": None,
        "unit": "%",
        "scale": 0.1,
        "entity_type": "sensor",
        "icon": "mdi:pump",
    },

    # ─── Module 0# Temperatures ───
    # NOTE: IR[135] (~81°C) and IR[136] (0°C) were previously mis-mapped as plate HX
    # water temperatures. IR[135] is actually a refrigerant-side temperature (condenser),
    # IR[136] appears unused/disconnected. Correct water temps are HR[1348]/HR[1349].
    137: {
        "name": "module_water_outlet_temperature",
        "device_class": "temperature",
        "unit": "°C",
        "scale": 0.1,
        "entity_type": "sensor",
    },
    138: {
        "name": "module_ambient_temperature",
        "device_class": "temperature",
        "unit": "°C",
        "scale": 0.1,
        "entity_type": "sensor",
    },
}

# ── Coils (pulse-based, FC05) ──
# BataviaHeat uses separate coils per direction (no toggle).
# Each write is a pulse (0xFF00) — there is no readable coil state.
# The current state is inferred from holding registers.
COILS: dict[int, dict] = {
    1024: {
        "name": "unit_power",
        "on_coil": 1024,
        "off_coil": 1025,
        "entity_type": "switch",
        "icon": "mdi:power",
        # HR[912] unit power mirror: 0=off, 1=on (more reliable than HR[768])
        "state_register": {"type": "holding", "address": 912},
    },
    1073: {
        "name": "silent_mode",
        "on_coil": 1073,
        "off_coil": 1074,
        "entity_type": "switch",
        "icon": "mdi:volume-off",
        # HR[913] silent-mode bitfield: 0=off, 1=L1, 3=L2 (>0 = silent on)
        "state_register": {"type": "holding", "address": 913},
    },
    1076: {
        "name": "silent_level_2",
        "on_coil": 1076,
        "off_coil": 1075,
        "entity_type": "switch",
        "icon": "mdi:volume-low",
        "requires": 1073,  # Only available when silent_mode is ON
    },
}

# Discrete inputs (read-only boolean) - FC02
# Not yet discovered. Needs dedicated discrete input scan.
DISCRETE_INPUTS: dict[int, dict] = {}

# Error code mapping (not yet identified)
ERROR_CODES: dict[int, str] = {}

# ── Cloud registers ─────────────────────────────────────────────────────────
# Keyed by cloud-API address (int).  These are a completely different numbering
# scheme from the raw Modbus addresses above (1000-4xxx vs. 22-7239).
# Values returned by paramListV3 are already human-readable floats — scale=1.
#
# "cloud_unique": True  → always shown when cloud is configured (no Modbus
#                          equivalent, or cloud provides distinct data).
# "cloud_unique": False → only shown when Modbus is NOT configured; when
#                          Modbus is enabled the local register is preferred.

# Shared enum for the per-zone heating/cooling climate curves (cloud 1046/1047/
# 1049). 0 = off, 1-8 = low-temp presets, 9-16 = high-temp presets, 17-20 =
# 2P/SOT curves. Values mirror the EcoHome app's climate-curve selector.
_CLOUD_CURVE_OPTIONS: dict[int, str] = {
    0: "off",
    1: "low_temp_1", 2: "low_temp_2", 3: "low_temp_3", 4: "low_temp_4",
    5: "low_temp_5", 6: "low_temp_6", 7: "low_temp_7", 8: "low_temp_8",
    9: "high_temp_1", 10: "high_temp_2", 11: "high_temp_3", 12: "high_temp_4",
    13: "high_temp_5", 14: "high_temp_6", 15: "high_temp_7", 16: "high_temp_8",
    17: "curve_2p_9", 18: "curve_2p_10", 19: "curve_sot_11", 20: "curve_sot_12",
}

CLOUD_REGISTERS: dict[int, dict] = {
    # ── Read-only sensors ──────────────────────────────────────────────────────
    2097: {
        "name": "room_temperature",
        "device_class": "temperature",
        "unit": "°C",
        "scale": 1,
        "entity_type": "sensor",
        "cloud_unique": True,
        "icon": "mdi:home-thermometer",
    },
    2072: {
        "name": "compressor_speed",
        "device_class": None,
        "unit": "rpm",
        "scale": 1,
        "entity_type": "sensor",
        "cloud_unique": True,
        "icon": "mdi:fan",
    },
    2100: {
        "name": "hot_water_tank_temperature",
        "device_class": "temperature",
        "unit": "°C",
        "scale": 1,
        "entity_type": "sensor",
        "cloud_unique": True,
        "icon": "mdi:water-boiler",
    },
    2104: {
        "name": "buffer_top_temperature",
        "device_class": "temperature",
        "unit": "°C",
        "scale": 1,
        "entity_type": "sensor",
        "cloud_unique": True,
        "icon": "mdi:storage-tank",
    },
    2105: {
        "name": "buffer_bottom_temperature",
        "device_class": "temperature",
        "unit": "°C",
        "scale": 1,
        "entity_type": "sensor",
        "cloud_unique": True,
        "icon": "mdi:storage-tank",
    },
    2099: {
        "name": "cloud_outdoor_temperature",
        "device_class": "temperature",
        "unit": "°C",
        "scale": 1,
        "entity_type": "sensor",
        "cloud_unique": False,
    },
    2102: {
        "name": "cloud_system_water_outlet_temperature",
        "device_class": "temperature",
        "unit": "°C",
        "scale": 1,
        "entity_type": "sensor",
        "cloud_unique": False,
    },
    2106: {
        "name": "cloud_hp_water_outlet_temperature",
        "device_class": "temperature",
        "unit": "°C",
        "scale": 1,
        "entity_type": "sensor",
        "cloud_unique": False,
    },
    2142: {
        "name": "cloud_fin_coil_temperature",
        "device_class": "temperature",
        "unit": "°C",
        "scale": 1,
        "entity_type": "sensor",
        "cloud_unique": False,
    },
    2143: {
        "name": "cloud_discharge_temperature",
        "device_class": "temperature",
        "unit": "°C",
        "scale": 1,
        "entity_type": "sensor",
        "cloud_unique": False,
    },
    2144: {
        "name": "cloud_suction_temperature",
        "device_class": "temperature",
        "unit": "°C",
        "scale": 1,
        "entity_type": "sensor",
        "cloud_unique": False,
    },
    2149: {
        "name": "cloud_low_pressure",
        "device_class": "pressure",
        "unit": "bar",
        "scale": 1,
        "entity_type": "sensor",
        "cloud_unique": False,
    },
    2150: {
        "name": "cloud_high_pressure",
        "device_class": "pressure",
        "unit": "bar",
        "scale": 1,
        "entity_type": "sensor",
        "cloud_unique": False,
    },
    2187: {
        "name": "cloud_plate_hx_water_inlet_temperature",
        "device_class": "temperature",
        "unit": "°C",
        "scale": 1,
        "entity_type": "sensor",
        "cloud_unique": False,
    },
    2188: {
        "name": "cloud_plate_hx_water_outlet_temperature",
        "device_class": "temperature",
        "unit": "°C",
        "scale": 1,
        "entity_type": "sensor",
        "cloud_unique": False,
    },
    2189: {
        "name": "cloud_total_water_outlet_temperature",
        "device_class": "temperature",
        "unit": "°C",
        "scale": 1,
        "entity_type": "sensor",
        "cloud_unique": False,
    },
    2191: {
        "name": "cloud_pump_target_speed",
        "device_class": None,
        "unit": "rpm",
        "scale": 1,
        "entity_type": "sensor",
        "cloud_unique": False,
        "icon": "mdi:pump",
    },
    2192: {
        "name": "cloud_pump_flow_rate",
        "device_class": None,
        "unit": "L/h",
        "scale": 1,
        "entity_type": "sensor",
        "cloud_unique": False,
        "icon": "mdi:water-pump",
    },
    2193: {
        "name": "cloud_pump_control_signal",
        "device_class": None,
        "unit": "%",
        "scale": 1,
        "entity_type": "sensor",
        "cloud_unique": False,
        "icon": "mdi:pump",
    },
    2194: {
        "name": "cloud_pump_feedback_signal",
        "device_class": None,
        "unit": "%",
        "scale": 1,
        "entity_type": "sensor",
        "cloud_unique": False,
        "icon": "mdi:pump",
    },
    # ── Cloud-only sensors added in the updated EcoHome app ──────────────────
    # These have no Modbus equivalent. On units that lack the corresponding
    # hardware (no DHW/solar/underfloor loop) the cloud reports "N/A"; such
    # entities auto-hide via the entity registry until a value appears.
    2011: {
        "name": "cloud_adjustable_target_temperature",
        "device_class": "temperature",
        "unit": "°C",
        "scale": 1,
        "entity_type": "sensor",
        "cloud_unique": True,
        "icon": "mdi:thermometer",
    },
    2103: {
        "name": "cloud_solar_boiler_temperature",
        "device_class": "temperature",
        "unit": "°C",
        "scale": 1,
        "entity_type": "sensor",
        "cloud_unique": True,
        "icon": "mdi:solar-power",
    },
    2111: {
        "name": "cloud_floor_heating_inlet_temperature",
        "device_class": "temperature",
        "unit": "°C",
        "scale": 1,
        "entity_type": "sensor",
        "cloud_unique": True,
        "icon": "mdi:heating-coil",
    },
    2195: {
        "name": "cloud_pump_fault_info",
        "device_class": None,
        "unit": None,
        "scale": 1,
        "entity_type": "sensor",
        "cloud_unique": True,
        "icon": "mdi:pump-off",
    },
    # ── Writable settings (always shown when cloud is configured) ─────────────
    1024: {
        "name": "hot_water_setpoint",
        "device_class": "temperature",
        "unit": "°C",
        "scale": 1,
        "min": 18,
        "max": 75,
        "entity_type": "number",
        "cloud_unique": True,
        "icon": "mdi:water-boiler",
    },
    1022: {
        "name": "cloud_cooling_setpoint",
        "device_class": "temperature",
        "unit": "°C",
        "scale": 1,
        "min": 10,
        "max": 35,
        "entity_type": "number",
        "cloud_unique": False,
    },
    1023: {
        "name": "cloud_heating_setpoint",
        "device_class": "temperature",
        "unit": "°C",
        "scale": 1,
        "min": 20,
        "max": 80,
        "entity_type": "number",
        "cloud_unique": False,
    },
    1029: {
        "name": "cloud_heating_setpoint_zone_b",
        "device_class": "temperature",
        "unit": "°C",
        "scale": 1,
        "min": 20,
        "max": 70,
        "entity_type": "number",
        "cloud_unique": False,
    },
    1004: {
        "name": "cloud_silent_mode",
        "device_class": None,
        "unit": None,
        "scale": 1,
        "entity_type": "select",
        "cloud_unique": False,
        "options": {0: "off", 1: "on"},
        "icon": "mdi:volume-off",
    },
    1031: {
        "name": "cloud_power_mode",
        "device_class": None,
        "unit": None,
        "scale": 1,
        "entity_type": "select",
        "cloud_unique": False,
        "options": {0: "standard", 1: "powerful", 2: "eco", 3: "auto"},
        "icon": "mdi:lightning-bolt",
    },
    # ── Cloud-first climate curves & display settings (updated app) ──────────
    # Per-zone curve selectors. Many users run cloud-only, so these are always
    # shown when cloud is configured (cloud_unique=True) even though a coarser
    # heating-curve register also exists on Modbus.
    1046: {
        "name": "cloud_cooling_curve_zone_a",
        "device_class": None,
        "unit": None,
        "scale": 1,
        "entity_type": "select",
        "cloud_unique": True,
        "options": _CLOUD_CURVE_OPTIONS,
        "icon": "mdi:chart-bell-curve",
    },
    1047: {
        "name": "cloud_heating_curve_zone_a",
        "device_class": None,
        "unit": None,
        "scale": 1,
        "entity_type": "select",
        "cloud_unique": True,
        "options": _CLOUD_CURVE_OPTIONS,
        "icon": "mdi:chart-bell-curve",
    },
    1049: {
        "name": "cloud_heating_curve_zone_b",
        "device_class": None,
        "unit": None,
        "scale": 1,
        "entity_type": "select",
        "cloud_unique": True,
        "options": _CLOUD_CURVE_OPTIONS,
        "icon": "mdi:chart-bell-curve",
    },
    4112: {
        "name": "cloud_light_strip_brightness",
        "device_class": None,
        "unit": "%",
        "scale": 1,
        "min": 10,
        "max": 100,
        "entity_type": "number",
        "cloud_unique": True,
        "icon": "mdi:brightness-6",
    },
    4111: {
        "name": "cloud_light_strip",
        "device_class": None,
        "unit": None,
        "scale": 1,
        "entity_type": "select",
        "cloud_unique": True,
        "options": {0: "off", 1: "on"},
        "icon": "mdi:led-strip-variant",
    },
}

