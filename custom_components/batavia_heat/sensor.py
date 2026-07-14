"""Sensor platform for BataviaHeat R290."""
from __future__ import annotations

from datetime import datetime, timezone

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    PERCENTAGE,
    UnitOfElectricCurrent,
    UnitOfElectricPotential,
    UnitOfEnergy,
    UnitOfFrequency,
    UnitOfPower,
    UnitOfPressure,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity

from .const import CALCULATED_SENSORS, CLOUD_REGISTERS, CONF_ENERGY_ENTITY, DOMAIN, INPUT_REGISTERS, HOLDING_REGISTERS
from .coordinator import BataviaHeatCoordinator
from .entity import BataviaHeatEntity

# Map unit strings to HA unit constants
UNIT_MAP = {
    "°C": UnitOfTemperature.CELSIUS,
    "Hz": UnitOfFrequency.HERTZ,
    "bar": UnitOfPressure.BAR,
    "W": UnitOfPower.WATT,
    "kW": UnitOfPower.KILO_WATT,
    "kWh": UnitOfEnergy.KILO_WATT_HOUR,
    "A": UnitOfElectricCurrent.AMPERE,
    "V": UnitOfElectricPotential.VOLT,
    "%": PERCENTAGE,
    "rpm": "rpm",
    "L/h": "L/h",
}

DEVICE_CLASS_MAP = {
    "temperature": SensorDeviceClass.TEMPERATURE,
    "frequency": SensorDeviceClass.FREQUENCY,
    "pressure": SensorDeviceClass.PRESSURE,
    "power": SensorDeviceClass.POWER,
    "energy": SensorDeviceClass.ENERGY,
    "voltage": SensorDeviceClass.VOLTAGE,
    "current": SensorDeviceClass.CURRENT,
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up BataviaHeat sensor entities."""
    coordinator: BataviaHeatCoordinator = hass.data[DOMAIN][entry.entry_id]
    entities: list[BataviaHeatSensor] = []

    # Sensors from input registers
    for addr, reg_info in INPUT_REGISTERS.items():
        if reg_info.get("entity_type") == "sensor":
            entities.append(BataviaHeatSensor(coordinator, "input", addr, reg_info))

    # Sensors from holding registers (read-only display)
    for addr, reg_info in HOLDING_REGISTERS.items():
        if reg_info.get("entity_type") == "sensor":
            entities.append(BataviaHeatSensor(coordinator, "holding", addr, reg_info))

    # Calculated sensors (derived from multiple registers)
    for key, calc_info in CALCULATED_SENSORS.items():
        entities.append(BataviaHeatCalculatedSensor(coordinator, key, calc_info))

    # Cloud sensors (when cloud connection is configured)
    from .const import CONNECTION_CLOUD
    entry = coordinator.config_entry
    if entry.data.get("connection_type") == CONNECTION_CLOUD:
        modbus_enabled = entry.data.get("modbus_enabled", False)
        for addr, reg_info in CLOUD_REGISTERS.items():
            if reg_info.get("entity_type") != "sensor":
                continue
            # Only show cloud-duplicate sensors when Modbus is NOT configured
            if not reg_info.get("cloud_unique", True) and modbus_enabled:
                continue
            entities.append(BataviaHeatSensor(coordinator, "cloud", addr, reg_info))

    # Energy integration sensor (built-in Riemann sum)
    entities.append(BataviaHeatEnergySensor(
        coordinator,
        key="energy_delivered",
        name="energy_delivered",
        icon="mdi:fire",
        power_source="thermal_power",
        power_unit_watts=False,
    ))

    # Cooling energy integration sensor (built-in Riemann sum)
    entities.append(BataviaHeatEnergySensor(
        coordinator,
        key="cooling_energy_delivered",
        name="cooling_energy_delivered",
        icon="mdi:snowflake",
        power_source="cooling_power",
        power_unit_watts=False,
    ))

    # COP (heating) + EER (cooling) sensors — only when an energy entity is set
    energy_entity_id = entry.options.get(CONF_ENERGY_ENTITY, "")
    if energy_entity_id:
        entities.append(BataviaHeatCOPCurrentSensor(coordinator, energy_entity_id))
        entities.append(
            BataviaHeatCOPCurrentSensor(coordinator, energy_entity_id, mode="cooling")
        )
        for period in ("today", "week", "month", "year", "alltime"):
            entities.append(
                BataviaHeatCOPPeriodSensor(coordinator, period, energy_entity_id)
            )
            entities.append(
                BataviaHeatCOPPeriodSensor(
                    coordinator, period, energy_entity_id, mode="cooling"
                )
            )

    async_add_entities(entities)


class BataviaHeatSensor(BataviaHeatEntity, SensorEntity):
    """Representation of a BataviaHeat sensor."""

    def __init__(
        self,
        coordinator: BataviaHeatCoordinator,
        reg_type: str,
        address: int,
        reg_info: dict,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, reg_type, address, reg_info)

        # Device class
        if dc := reg_info.get("device_class"):
            self._attr_device_class = DEVICE_CLASS_MAP.get(dc)

        # Unit of measurement
        if unit := reg_info.get("unit"):
            self._attr_native_unit_of_measurement = UNIT_MAP.get(unit, unit)

        # State class — override from register definition (e.g. total_increasing for energy)
        sc = reg_info.get("state_class")
        if sc == "total_increasing":
            self._attr_state_class = SensorStateClass.TOTAL_INCREASING
        else:
            self._attr_state_class = SensorStateClass.MEASUREMENT

    @property
    def native_value(self) -> float | None:
        """Return the sensor value."""
        if self.coordinator.data is None:
            return None
        return self.coordinator.data.get(self._reg_type, {}).get(self._address)


class BataviaHeatCalculatedSensor(SensorEntity):
    """Sensor calculated from multiple Modbus registers."""

    _attr_has_entity_name = True
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(
        self,
        coordinator: BataviaHeatCoordinator,
        key: str,
        calc_info: dict,
    ) -> None:
        """Initialize the calculated sensor."""
        self.coordinator = coordinator
        self._key = key
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_calc_{key}"
        self._attr_translation_key = calc_info["name"]

        if dc := calc_info.get("device_class"):
            self._attr_device_class = DEVICE_CLASS_MAP.get(dc)
        if unit := calc_info.get("unit"):
            self._attr_native_unit_of_measurement = UNIT_MAP.get(unit, unit)
        if icon := calc_info.get("icon"):
            self._attr_icon = icon

    @property
    def device_info(self):
        """Return device info."""
        from .const import MANUFACTURER, MODEL
        from homeassistant.helpers.device_registry import DeviceInfo
        return DeviceInfo(
            identifiers={(DOMAIN, self.coordinator.config_entry.entry_id)},
            name="BataviaHeat R290",
            manufacturer=MANUFACTURER,
            model=MODEL,
        )

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return self.coordinator.last_update_success and self.coordinator.data is not None

    @property
    def native_value(self) -> float | None:
        """Return the calculated sensor value."""
        if self.coordinator.data is None:
            return None
        data = self.coordinator.data

        if self._key == "thermal_power":
            # thermal_power = flow_rate(L/h) × (outlet−inlet)(°C) × 4.186(J/g·°C) / 3600
            # Result in kW. Modbus data preferred; cloud data used as fallback.
            holding = data.get("holding", {})
            inp = data.get("input", {})
            cloud = data.get("cloud", {})

            flow   = inp.get(54)       or cloud.get(2192)   # L/h
            inlet  = holding.get(1348) or cloud.get(2187)   # °C water inlet plate HX
            outlet = holding.get(1349) or cloud.get(2188)   # °C water outlet plate HX

            if flow is None or inlet is None or outlet is None:
                return None
            if flow <= 0:
                return 0.0
            result = round(flow * (outlet - inlet) * 4.186 / 3600, 3)
            # Sanity check: 3-8kW heat pump, max ~15kW realistic
            if abs(result) > 30:
                return None
            # Heating mode: thermal power should be positive
            return max(result, 0.0)

        if self._key == "cooling_power":
            # cooling_power = flow_rate(L/h) × (inlet−outlet)(°C) × 4.186 / 3600
            # Positive magnitude while cooling (outlet < inlet); 0 while heating.
            holding = data.get("holding", {})
            inp = data.get("input", {})
            cloud = data.get("cloud", {})

            flow   = inp.get(54)       or cloud.get(2192)   # L/h
            inlet  = holding.get(1348) or cloud.get(2187)   # °C water inlet plate HX
            outlet = holding.get(1349) or cloud.get(2188)   # °C water outlet plate HX

            if flow is None or inlet is None or outlet is None:
                return None
            if flow <= 0:
                return 0.0
            result = round(flow * (outlet - inlet) * 4.186 / 3600, 3)
            if abs(result) > 30:
                return None
            # Cooling: outlet < inlet → result negative → return magnitude.
            return max(-result, 0.0)

        return None

    async def async_added_to_hass(self) -> None:
        """Register update listener."""
        self.async_on_remove(
            self.coordinator.async_add_listener(self.async_write_ha_state)
        )


class BataviaHeatEnergySensor(RestoreEntity, SensorEntity):
    """Energy sensor with built-in Riemann sum integration.

    Integrates a power source (W or kW) over time to produce kWh.
    Uses RestoreEntity to persist the accumulated value across HA restarts.
    Uses state_class TOTAL_INCREASING so HA's energy dashboard accepts it.
    """

    _attr_has_entity_name = True
    _attr_device_class = SensorDeviceClass.ENERGY
    _attr_native_unit_of_measurement = UnitOfEnergy.KILO_WATT_HOUR
    _attr_state_class = SensorStateClass.TOTAL_INCREASING

    def __init__(
        self,
        coordinator: BataviaHeatCoordinator,
        key: str,
        name: str,
        icon: str,
        power_source: tuple[str, int] | str,
        power_unit_watts: bool,
    ) -> None:
        """Initialize the energy sensor.

        Args:
            power_source: Either (reg_type, address) tuple for a register,
                          or a string key for a calculated sensor.
            power_unit_watts: True if source is in W, False if in kW.
        """
        self.coordinator = coordinator
        self._key = key
        self._power_source = power_source
        self._power_unit_watts = power_unit_watts
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_energy_{key}"
        self._attr_translation_key = name
        self._attr_icon = icon
        self._accumulated: float = 0.0
        self._last_update: datetime | None = None

    @property
    def device_info(self):
        """Return device info."""
        from .const import MANUFACTURER, MODEL
        from homeassistant.helpers.device_registry import DeviceInfo
        return DeviceInfo(
            identifiers={(DOMAIN, self.coordinator.config_entry.entry_id)},
            name="BataviaHeat R290",
            manufacturer=MANUFACTURER,
            model=MODEL,
        )

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return self.coordinator.last_update_success and self.coordinator.data is not None

    @property
    def native_value(self) -> float | None:
        """Return the accumulated energy in kWh."""
        return round(self._accumulated, 3)

    def _get_power_kw(self) -> float | None:
        """Get current power in kW from the source."""
        if self.coordinator.data is None:
            return None
        data = self.coordinator.data

        if isinstance(self._power_source, tuple):
            reg_type, addr = self._power_source
            val = data.get(reg_type, {}).get(addr)
            if val is None:
                return None
            return val / 1000.0 if self._power_unit_watts else val

        # Calculated sensor: compute inline
        if self._power_source == "thermal_power":
            flow = data.get("input", {}).get(54)
            inlet = data.get("holding", {}).get(1348)
            outlet = data.get("holding", {}).get(1349)
            if flow is None or inlet is None or outlet is None or flow <= 0:
                return 0.0
            return flow * (outlet - inlet) * 4.186 / 3600

        if self._power_source == "cooling_power":
            flow = data.get("input", {}).get(54)
            inlet = data.get("holding", {}).get(1348)
            outlet = data.get("holding", {}).get(1349)
            if flow is None or inlet is None or outlet is None or flow <= 0:
                return 0.0
            # Cooling magnitude (positive while cooling, 0 while heating)
            return max(-(flow * (outlet - inlet) * 4.186 / 3600), 0.0)

        return None

    def _integrate(self) -> None:
        """Perform trapezoidal integration step."""
        now = datetime.now(timezone.utc)
        power_kw = self._get_power_kw()

        if power_kw is not None and power_kw >= 0 and self._last_update is not None:
            dt_hours = (now - self._last_update).total_seconds() / 3600.0
            if 0 < dt_hours < 1:  # Skip if gap > 1 hour (HA was offline)
                self._accumulated += power_kw * dt_hours

        self._last_update = now

    async def async_added_to_hass(self) -> None:
        """Restore state and register update listener."""
        if (last_state := await self.async_get_last_state()) is not None:
            if last_state.state not in (None, "unknown", "unavailable"):
                try:
                    self._accumulated = float(last_state.state)
                except (ValueError, TypeError):
                    pass

        # Set initial timestamp (don't integrate first interval after restart)
        self._last_update = datetime.now(timezone.utc)

        def _on_update() -> None:
            self._integrate()
            self.async_write_ha_state()

        self.async_on_remove(
            self.coordinator.async_add_listener(_on_update)
        )


def _compute_thermal_power_kw(data: dict) -> float | None:
    """Compute thermal power in kW from coordinator data."""
    flow = data.get("input", {}).get(54)
    inlet = data.get("holding", {}).get(1348)
    outlet = data.get("holding", {}).get(1349)
    if flow is None or inlet is None or outlet is None:
        return None
    if flow <= 0:
        return 0.0
    result = flow * (outlet - inlet) * 4.186 / 3600
    if abs(result) > 30:
        return None
    return max(result, 0.0)


def _compute_cooling_power_kw(data: dict) -> float | None:
    """Compute cooling power in kW (positive magnitude) from coordinator data.

    Cooling chills the water (outlet < inlet) so the raw thermal figure is
    negative; this returns its magnitude, and 0 while heating.
    """
    flow = data.get("input", {}).get(54)
    inlet = data.get("holding", {}).get(1348)
    outlet = data.get("holding", {}).get(1349)
    if flow is None:
        flow = data.get("cloud", {}).get(2192)
    if inlet is None:
        inlet = data.get("cloud", {}).get(2187)
    if outlet is None:
        outlet = data.get("cloud", {}).get(2188)
    if flow is None or inlet is None or outlet is None:
        return None
    if flow <= 0:
        return 0.0
    result = flow * (outlet - inlet) * 4.186 / 3600
    if abs(result) > 30:
        return None
    return max(-result, 0.0)


class BataviaHeatCOPCurrentSensor(SensorEntity):
    """Instantaneous COP derived from thermal power and electrical power.

    Electrical power is computed from the rate of change of the external
    kWh meter. COP = thermal_power_kw / electrical_power_kw.
    """

    _attr_has_entity_name = True
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_icon = "mdi:speedometer"
    _attr_suggested_display_precision = 1

    def __init__(
        self,
        coordinator: BataviaHeatCoordinator,
        energy_entity_id: str,
        mode: str = "heating",
    ) -> None:
        """Initialize the instantaneous COP/EER sensor."""
        self.coordinator = coordinator
        self._energy_entity_id = energy_entity_id
        self._mode = mode
        self._power_fn = (
            _compute_cooling_power_kw if mode == "cooling" else _compute_thermal_power_kw
        )
        prefix = "eer" if mode == "cooling" else "cop"
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_{prefix}_current"
        self._attr_translation_key = f"{prefix}_current"
        self._attr_icon = (
            "mdi:snowflake-thermometer" if mode == "cooling" else "mdi:speedometer"
        )
        self._cop_value: float | None = None
        self._prev_kwh: float | None = None
        self._prev_time: datetime | None = None

    @property
    def device_info(self):
        """Return device info."""
        from .const import MANUFACTURER, MODEL
        from homeassistant.helpers.device_registry import DeviceInfo
        return DeviceInfo(
            identifiers={(DOMAIN, self.coordinator.config_entry.entry_id)},
            name="BataviaHeat R290",
            manufacturer=MANUFACTURER,
            model=MODEL,
        )

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return self.coordinator.last_update_success and self.coordinator.data is not None

    @property
    def native_value(self) -> float | None:
        """Return the current COP."""
        return self._cop_value

    def _update_cop(self) -> None:
        """Compute instantaneous COP from thermal power and meter delta."""
        if self.coordinator.data is None:
            return
        thermal_kw = self._power_fn(self.coordinator.data)

        # Derive electrical power from kWh meter rate of change
        state = self.hass.states.get(self._energy_entity_id)
        electrical_kw: float | None = None
        if state and state.state not in ("unknown", "unavailable"):
            try:
                current_kwh = float(state.state)
            except (ValueError, TypeError):
                current_kwh = None

            if current_kwh is not None:
                now = datetime.now(timezone.utc)
                if self._prev_kwh is not None and self._prev_time is not None:
                    dt_hours = (now - self._prev_time).total_seconds() / 3600.0
                    if 0 < dt_hours < 0.5:
                        delta = current_kwh - self._prev_kwh
                        if delta >= 0:
                            electrical_kw = delta / dt_hours
                self._prev_kwh = current_kwh
                self._prev_time = now

        if thermal_kw is not None and electrical_kw is not None and electrical_kw > 0.05:
            cop = thermal_kw / electrical_kw
            self._cop_value = round(cop, 1) if cop <= 15 else None
        elif thermal_kw is not None and thermal_kw < 0.01:
            self._cop_value = 0.0
        else:
            self._cop_value = None

    async def async_added_to_hass(self) -> None:
        """Register update listener."""
        self._prev_time = datetime.now(timezone.utc)

        def _on_update() -> None:
            self._update_cop()
            self.async_write_ha_state()

        self.async_on_remove(
            self.coordinator.async_add_listener(_on_update)
        )


# Bump this when COP accumulation logic or register sources change.
# Forces a clean reset instead of restoring stale/incompatible state.
_COP_STATE_VERSION = 2


class BataviaHeatCOPPeriodSensor(RestoreEntity, SensorEntity):
    """COP sensor for a specific time period (today/week/month/year/alltime).

    Accumulates thermal energy via Riemann integration and reads electrical
    energy from an external kWh meter. Both accumulators advance only when
    thermal data is available (paired accumulation) to prevent COP skew
    from asymmetric data gaps.
    """

    _attr_has_entity_name = True
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_icon = "mdi:speedometer"
    _attr_suggested_display_precision = 1

    def __init__(
        self,
        coordinator: BataviaHeatCoordinator,
        period: str,
        energy_entity_id: str,
        mode: str = "heating",
    ) -> None:
        """Initialize the period COP/EER sensor."""
        self.coordinator = coordinator
        self._period = period
        self._energy_entity_id = energy_entity_id
        self._mode = mode
        self._power_fn = (
            _compute_cooling_power_kw if mode == "cooling" else _compute_thermal_power_kw
        )
        prefix = "eer" if mode == "cooling" else "cop"
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_{prefix}_{period}"
        self._attr_translation_key = f"{prefix}_{period}"
        self._attr_icon = (
            "mdi:snowflake-thermometer" if mode == "cooling" else "mdi:speedometer"
        )

        self._accumulated_thermal: float = 0.0
        self._accumulated_electrical: float = 0.0
        self._prev_electrical_kwh: float | None = None
        self._install_date: datetime | None = None
        self._period_key: str | None = None
        self._last_update: datetime | None = None
        self._cop_value: float | None = None

    @property
    def device_info(self):
        """Return device info."""
        from .const import MANUFACTURER, MODEL
        from homeassistant.helpers.device_registry import DeviceInfo
        return DeviceInfo(
            identifiers={(DOMAIN, self.coordinator.config_entry.entry_id)},
            name="BataviaHeat R290",
            manufacturer=MANUFACTURER,
            model=MODEL,
        )

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return self.coordinator.last_update_success and self.coordinator.data is not None

    @property
    def native_value(self) -> float | None:
        """Return the COP for this period."""
        return self._cop_value

    @property
    def extra_state_attributes(self) -> dict:
        """Expose metadata for state restoration and diagnostics."""
        return {
            "state_version": _COP_STATE_VERSION,
            "install_date": self._install_date.isoformat() if self._install_date else None,
            "period": self._period,
            "period_key": self._period_key,
            "accumulated_thermal_kwh": round(self._accumulated_thermal, 6),
            "accumulated_electrical_kwh": round(self._accumulated_electrical, 6),
        }

    @staticmethod
    def _period_key_for(period: str, dt: datetime) -> str:
        """Return the period key string for a given datetime (local time)."""
        local = dt.astimezone()
        if period == "today":
            return local.strftime("%Y-%m-%d")
        if period == "week":
            iso = local.isocalendar()
            return f"{iso[0]}-W{iso[1]:02d}"
        if period == "month":
            return local.strftime("%Y-%m")
        if period == "year":
            return local.strftime("%Y")
        return "alltime"

    def _read_electrical_kwh(self) -> float | None:
        """Read current kWh value from the external energy entity."""
        state = self.hass.states.get(self._energy_entity_id)
        if state is None or state.state in ("unknown", "unavailable"):
            return None
        try:
            return float(state.state)
        except (ValueError, TypeError):
            return None

    def _reset_period(self) -> None:
        """Reset accumulated values for a new period."""
        self._accumulated_thermal = 0.0
        self._accumulated_electrical = 0.0
        self._prev_electrical_kwh = self._read_electrical_kwh()
        self._cop_value = None

    def _update(self) -> None:
        """Accumulate thermal and electrical energy and compute period COP.

        PAIRED ACCUMULATION: both thermal and electrical only advance when
        thermal data is available (not None). This prevents COP skew when
        Modbus reads fail (thermal=None) but the external kWh meter keeps
        counting. The electrical meter position is always tracked so that
        we don't "catch up" with a large delta after a data gap.
        """
        now = datetime.now(timezone.utc)

        # Check for period rollover
        new_key = self._period_key_for(self._period, now)
        if self._period_key is not None and new_key != self._period_key:
            self._reset_period()
        self._period_key = new_key

        # Determine if this interval is valid (gap < 1 hour)
        valid_interval = False
        dt_hours = 0.0
        if self._last_update is not None:
            dt_hours = (now - self._last_update).total_seconds() / 3600.0
            valid_interval = 0 < dt_hours < 1

        # Read current values
        thermal_kw = None
        if self.coordinator.data is not None:
            thermal_kw = self._power_fn(self.coordinator.data)
        current_electrical = self._read_electrical_kwh()

        # PAIRED accumulation: only accumulate BOTH when thermal is valid.
        # thermal_kw=0.0 (pump off) is valid — standby power correctly
        # enters the denominator. thermal_kw=None (data missing) skips both.
        if valid_interval and thermal_kw is not None:
            self._accumulated_thermal += thermal_kw * dt_hours
            if current_electrical is not None and self._prev_electrical_kwh is not None:
                delta = current_electrical - self._prev_electrical_kwh
                if delta >= 0:
                    self._accumulated_electrical += delta

        # Always track meter position to prevent delta catch-up after gaps
        if current_electrical is not None:
            self._prev_electrical_kwh = current_electrical

        self._last_update = now

        # Calculate COP
        if self._accumulated_electrical > 0.01:
            cop = self._accumulated_thermal / self._accumulated_electrical
            self._cop_value = round(cop, 1) if cop <= 15 else None
        elif self._accumulated_thermal < 0.001:
            self._cop_value = 0.0
        else:
            self._cop_value = None

    async def async_added_to_hass(self) -> None:
        """Restore state and register update listener."""
        if (last_state := await self.async_get_last_state()) is not None:
            attrs = last_state.attributes or {}

            # Restore install date
            if install_str := attrs.get("install_date"):
                try:
                    self._install_date = datetime.fromisoformat(install_str)
                except (ValueError, TypeError):
                    pass

            # Only restore accumulators if state version matches AND
            # same period is still active. Version mismatch means the
            # calculation logic changed — old values would poison the COP.
            saved_version = attrs.get("state_version")
            saved_key = attrs.get("period_key")
            current_key = self._period_key_for(self._period, datetime.now(timezone.utc))

            if saved_version == _COP_STATE_VERSION and saved_key == current_key:
                try:
                    self._accumulated_thermal = float(
                        attrs.get("accumulated_thermal_kwh", 0)
                    )
                except (ValueError, TypeError):
                    self._accumulated_thermal = 0.0
                try:
                    self._accumulated_electrical = float(
                        attrs.get("accumulated_electrical_kwh", 0)
                    )
                except (ValueError, TypeError):
                    self._accumulated_electrical = 0.0

                if last_state.state not in (None, "unknown", "unavailable"):
                    try:
                        self._cop_value = float(last_state.state)
                    except (ValueError, TypeError):
                        pass

        # Set install date on first ever start
        if self._install_date is None:
            self._install_date = datetime.now(timezone.utc)

        self._period_key = self._period_key_for(
            self._period, datetime.now(timezone.utc)
        )
        self._last_update = datetime.now(timezone.utc)

        def _on_update() -> None:
            self._update()
            self.async_write_ha_state()

        self.async_on_remove(
            self.coordinator.async_add_listener(_on_update)
        )
