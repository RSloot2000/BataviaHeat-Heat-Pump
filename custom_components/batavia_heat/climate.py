"""Climate platform for BataviaHeat R290."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.climate import (
    ClimateEntity,
    ClimateEntityFeature,
    HVACAction,
    HVACMode,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import CONNECTION_CLOUD, DOMAIN, MANUFACTURER, MODEL
from .coordinator import BataviaHeatCoordinator
from .entity import BataviaHeatEntity

_LOGGER = logging.getLogger(__name__)

# Coil addresses for unit on/off (pulse-based, FC05)
COIL_UNIT_ON = 1024
COIL_UNIT_OFF = 1025

# Register addresses
REG_TARGET_TEMP = 772     # HR[772]: Calculated heating curve setpoint (°C, scale=0.1)
REG_WRITE_TEMP = 6402     # HR[6402]: Max heating temperature / M02 (°C, scale=1)
REG_CURRENT_TEMP = 1350   # HR[1350]: T80 total water outlet temperature (°C, scale=0.1)
REG_OP_STATUS = 768       # HR[768]: Operational status (0 = off, >0 = running)
REG_POWER_STATE = 912     # HR[912]: Unit power mirror (0 = off, 1 = on)
REG_CURVE_MODE = 6426     # HR[6426]: Heating curve mode (0 = off, >0 = curve active)
REG_WORKING_MODE = 6400   # HR[6400]: Working mode (1=cool, 2=heat, 3=auto)
REG_COMPRESSOR = 1283     # HR[1283]: Compressor running (0/1)
REG_POWER_MODE = 6465     # HR[6465]: N01 power mode (0=std,1=powerful,2=eco,3=auto)

# Cloud control addresses (from getDeviceDetailV3, NOT paramListV3).
# Used when only the cloud connection is available (no Modbus writes).
CLOUD_POWER_ADDRESS = 1017   # device on/off via updateSwitchSate (bool)
CLOUD_MODE_ADDRESS = 1021    # 1=cool, 2=heat, 3=auto via controlOfValue
CLOUD_COOL_SETPOINT = 1022   # cooling target temperature
CLOUD_HEAT_SETPOINT = 1023   # heating target temperature
CLOUD_COOL_CURVE = 1046      # cooling curve zone A (>0 = active)
CLOUD_HEAT_CURVE = 1047      # heating curve zone A (>0 = active)
CLOUD_COMPRESSOR_SPEED = 2072  # compressor rpm (>0 = actively running)

# Working-mode register value ↔ HVAC mode
_MODE_TO_HVAC = {1: HVACMode.COOL, 2: HVACMode.HEAT, 3: HVACMode.AUTO}
_HVAC_TO_MODE = {v: k for k, v in _MODE_TO_HVAC.items()}

# Power-mode register value ↔ preset name
_PRESET_TO_MODE = {"standard": 0, "powerful": 1, "eco": 2, "auto": 3}
_MODE_TO_PRESET = {v: k for k, v in _PRESET_TO_MODE.items()}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up BataviaHeat climate entity."""
    coordinator: BataviaHeatCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([BataviaHeatClimate(coordinator)])


class BataviaHeatClimate(BataviaHeatEntity, ClimateEntity):
    """Climate entity for BataviaHeat R290 heat pump (CV heating only)."""

    _attr_has_entity_name = True
    _attr_name = "Heat Pump"
    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_target_temperature_step = 1.0
    _attr_hvac_modes = [HVACMode.OFF, HVACMode.HEAT, HVACMode.COOL, HVACMode.AUTO]
    _attr_preset_modes = list(_PRESET_TO_MODE)
    # The single main entity uses cloud fallbacks; never auto-hide it.
    _auto_hide_when_missing = False

    def __init__(self, coordinator: BataviaHeatCoordinator) -> None:
        """Initialize the climate entity."""
        super().__init__(coordinator, "holding", REG_OP_STATUS, {
            "name": "climate",
            "icon": "mdi:heat-pump",
        })
        self._attr_supported_features = (
            ClimateEntityFeature.TARGET_TEMPERATURE
            | ClimateEntityFeature.PRESET_MODE
            | ClimateEntityFeature.TURN_ON
            | ClimateEntityFeature.TURN_OFF
        )

    @property
    def _use_cloud_control(self) -> bool:
        """True when only the cloud connection is available (no Modbus writes)."""
        entry = self.coordinator.config_entry
        return (
            entry.data.get("connection_type") == CONNECTION_CLOUD
            and not entry.data.get("modbus_enabled", False)
        )

    @property
    def min_temp(self) -> float:
        """Lower setpoint bound; cooling allows lower targets than heating."""
        return 10.0 if self.hvac_mode == HVACMode.COOL else 20.0

    @property
    def max_temp(self) -> float:
        """Upper setpoint bound; cooling caps lower than heating."""
        return 35.0 if self.hvac_mode == HVACMode.COOL else 60.0

    @property
    def _cloud_mode(self) -> int | None:
        """Return the cloud operation mode (1=cool/2=heat/3=auto), if known."""
        if self.coordinator.data is None:
            return None
        raw = self.coordinator.data.get("cloud", {}).get(CLOUD_MODE_ADDRESS)
        return int(raw) if raw is not None else None

    @property
    def _is_curve_active(self) -> bool:
        """Return True if a heating/cooling curve is active.

        Prefers the Modbus curve register (HR[6426]); falls back to the cloud
        curve selectors (1046 cooling / 1047 heating) when Modbus is absent.
        """
        if self.coordinator.data is None:
            return False
        curve = self.coordinator.data.get("holding", {}).get(REG_CURVE_MODE)
        if curve is not None:
            return curve > 0
        cloud = self.coordinator.data.get("cloud", {})
        cool = cloud.get(CLOUD_COOL_CURVE)
        heat = cloud.get(CLOUD_HEAT_CURVE)
        return bool((cool and cool > 0) or (heat and heat > 0))

    @property
    def current_temperature(self) -> float | None:
        """Return the current water outlet temperature.

        Reads HR[1350] from Modbus first; falls back to cloud address 2189
        (total water outlet) or 2106 (HP water outlet) when Modbus is absent.
        """
        if self.coordinator.data is None:
            return None
        val = self.coordinator.data.get("holding", {}).get(REG_CURRENT_TEMP)
        if val is None:
            cloud = self.coordinator.data.get("cloud", {})
            val = cloud.get(2189) or cloud.get(2106)
        return val

    @property
    def target_temperature(self) -> float | None:
        """Return the heating setpoint.

        Reads HR[772] from Modbus first; falls back to the cloud setpoint that
        matches the active mode (1022 cooling / 1023 heating) when Modbus is
        absent.
        """
        if self.coordinator.data is None:
            return None
        val = self.coordinator.data.get("holding", {}).get(REG_TARGET_TEMP)
        if val is None:
            cloud = self.coordinator.data.get("cloud", {})
            if self._cloud_mode == 1:
                val = cloud.get(CLOUD_COOL_SETPOINT)
            else:
                val = cloud.get(CLOUD_HEAT_SETPOINT)
        return val

    @property
    def _is_unit_on(self) -> bool:
        """Return True if the unit is powered on.

        Uses the Modbus power mirror (HR[912], fallback HR[768]); falls back to
        the cloud power state (address 1017) when Modbus is absent.
        """
        if self.coordinator.data is None:
            return False
        holding = self.coordinator.data.get("holding", {})
        power = holding.get(REG_POWER_STATE)
        if power is not None:
            return power > 0
        status = holding.get(REG_OP_STATUS)
        if status is not None:
            return status > 0
        cloud_power = self.coordinator.data.get("cloud", {}).get(CLOUD_POWER_ADDRESS)
        return cloud_power is not None and cloud_power > 0

    @property
    def hvac_mode(self) -> HVACMode:
        """Return current HVAC mode: OFF if powered down, else the working mode."""
        if not self._is_unit_on:
            return HVACMode.OFF
        mode = self.coordinator.data.get("holding", {}).get(REG_WORKING_MODE)
        if mode is None:
            mode = self._cloud_mode
        return _MODE_TO_HVAC.get(int(mode), HVACMode.HEAT) if mode is not None else HVACMode.HEAT

    @property
    def hvac_action(self) -> HVACAction:
        """Return what the unit is actually doing (compressor + working mode)."""
        if not self._is_unit_on:
            return HVACAction.OFF
        holding = self.coordinator.data.get("holding", {})
        running = holding.get(REG_COMPRESSOR)
        if running is None:
            speed = self.coordinator.data.get("cloud", {}).get(CLOUD_COMPRESSOR_SPEED)
            running = bool(speed and speed > 0)
        if not running:
            return HVACAction.IDLE
        mode = holding.get(REG_WORKING_MODE)
        if mode is None:
            mode = self._cloud_mode
        return HVACAction.COOLING if mode == 1 else HVACAction.HEATING

    @property
    def preset_mode(self) -> str | None:
        """Return current power mode (HR[6465]) as a preset."""
        if self.coordinator.data is None:
            return None
        raw = self.coordinator.data.get("holding", {}).get(REG_POWER_MODE)
        return _MODE_TO_PRESET.get(int(raw)) if raw is not None else None

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set new target temperature.

        Modbus: HR[6402] (only when the heating curve is off). Cloud-only:
        writes the setpoint that matches the active mode (1022 cool / 1023 heat).
        """
        if self._is_curve_active:
            _LOGGER.warning(
                "Cannot set temperature: a heating/cooling curve is active. "
                "Disable the curve first or adjust curve parameters."
            )
            return
        temp = kwargs.get("temperature")
        if temp is None:
            return
        if self._use_cloud_control:
            address = (
                CLOUD_COOL_SETPOINT if self._cloud_mode == 1 else CLOUD_HEAT_SETPOINT
            )
            await self.coordinator.async_cloud_set_value(address, int(temp))
        else:
            await self.coordinator.async_write_register(REG_WRITE_TEMP, int(temp))

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set working mode; OFF powers the unit down."""
        if self._use_cloud_control:
            if hvac_mode == HVACMode.OFF:
                await self.coordinator.async_cloud_set_switch(CLOUD_POWER_ADDRESS, False)
                return
            if (mode := _HVAC_TO_MODE.get(hvac_mode)) is not None:
                await self.coordinator.async_cloud_set_value(CLOUD_MODE_ADDRESS, mode)
            if not self._is_unit_on:
                await self.coordinator.async_cloud_set_switch(CLOUD_POWER_ADDRESS, True)
            return
        if hvac_mode == HVACMode.OFF:
            await self.coordinator.async_write_coil(COIL_UNIT_OFF, True)
            return
        if (mode := _HVAC_TO_MODE.get(hvac_mode)) is not None:
            await self.coordinator.async_write_register(REG_WORKING_MODE, mode)
        if not self._is_unit_on:
            await self.coordinator.async_write_coil(COIL_UNIT_ON, True)

    async def async_turn_on(self) -> None:
        """Power the unit on (separate from working mode)."""
        if self._use_cloud_control:
            await self.coordinator.async_cloud_set_switch(CLOUD_POWER_ADDRESS, True)
            return
        await self.coordinator.async_write_coil(COIL_UNIT_ON, True)

    async def async_turn_off(self) -> None:
        """Power the unit off (separate from working mode)."""
        if self._use_cloud_control:
            await self.coordinator.async_cloud_set_switch(CLOUD_POWER_ADDRESS, False)
            return
        await self.coordinator.async_write_coil(COIL_UNIT_OFF, True)

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        """Set the power mode (HR[6465]) from a preset."""
        if (raw := _PRESET_TO_MODE.get(preset_mode)) is not None:
            await self.coordinator.async_write_register(REG_POWER_MODE, raw)
