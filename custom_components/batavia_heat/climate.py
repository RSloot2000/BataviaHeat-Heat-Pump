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

from .const import DOMAIN, MANUFACTURER, MODEL
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
    _attr_min_temp = 20.0
    _attr_max_temp = 60.0
    _attr_hvac_modes = [HVACMode.OFF, HVACMode.HEAT, HVACMode.COOL, HVACMode.AUTO]
    _attr_preset_modes = list(_PRESET_TO_MODE)
    _enable_turn_on_off_backwards_compatibility = False

    def __init__(self, coordinator: BataviaHeatCoordinator) -> None:
        """Initialize the climate entity."""
        super().__init__(coordinator, "holding", REG_OP_STATUS, {
            "name": "climate",
            "icon": "mdi:heat-pump",
        })

    _attr_supported_features = (
        ClimateEntityFeature.TARGET_TEMPERATURE
        | ClimateEntityFeature.PRESET_MODE
        | ClimateEntityFeature.TURN_ON
        | ClimateEntityFeature.TURN_OFF
    )

    @property
    def _is_curve_active(self) -> bool:
        """Return True if heating curve mode is active (HR[6426] > 0)."""
        if self.coordinator.data is None:
            return False
        curve = self.coordinator.data.get("holding", {}).get(REG_CURVE_MODE)
        return curve is not None and curve > 0

    @property
    def current_temperature(self) -> float | None:
        """Return the current water outlet temperature (HR[776])."""
        if self.coordinator.data is None:
            return None
        return self.coordinator.data.get("holding", {}).get(REG_CURRENT_TEMP)

    @property
    def target_temperature(self) -> float | None:
        """Return the heating setpoint (HR[6402] = M02 parameter)."""
        if self.coordinator.data is None:
            return None
        return self.coordinator.data.get("holding", {}).get(REG_TARGET_TEMP)

    @property
    def _is_unit_on(self) -> bool:
        """Return True if the unit is powered on (HR[912] mirror, fallback HR[768])."""
        if self.coordinator.data is None:
            return False
        holding = self.coordinator.data.get("holding", {})
        power = holding.get(REG_POWER_STATE)
        if power is not None:
            return power > 0
        status = holding.get(REG_OP_STATUS)
        return status is not None and status > 0

    @property
    def hvac_mode(self) -> HVACMode:
        """Return current HVAC mode: OFF if powered down, else the working mode."""
        if not self._is_unit_on:
            return HVACMode.OFF
        mode = self.coordinator.data.get("holding", {}).get(REG_WORKING_MODE)
        return _MODE_TO_HVAC.get(int(mode), HVACMode.HEAT) if mode is not None else HVACMode.HEAT

    @property
    def hvac_action(self) -> HVACAction:
        """Return what the unit is actually doing (compressor + working mode)."""
        if not self._is_unit_on:
            return HVACAction.OFF
        running = self.coordinator.data.get("holding", {}).get(REG_COMPRESSOR)
        if not running:
            return HVACAction.IDLE
        mode = self.coordinator.data.get("holding", {}).get(REG_WORKING_MODE)
        return HVACAction.COOLING if mode == 1 else HVACAction.HEATING

    @property
    def preset_mode(self) -> str | None:
        """Return current power mode (HR[6465]) as a preset."""
        if self.coordinator.data is None:
            return None
        raw = self.coordinator.data.get("holding", {}).get(REG_POWER_MODE)
        return _MODE_TO_PRESET.get(int(raw)) if raw is not None else None

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set new target temperature via HR[6402] (scale=1, raw = temp).

        Only allowed when heating curve is off (HR[6426] = 0).
        """
        if self._is_curve_active:
            _LOGGER.warning(
                "Cannot set temperature: heating curve is active (HR[6426] > 0). "
                "Disable the heating curve first or adjust curve parameters."
            )
            return
        if (temp := kwargs.get("temperature")) is not None:
            await self.coordinator.async_write_register(REG_WRITE_TEMP, int(temp))

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set HVAC mode: pulse off coil for OFF, else set working mode + power on."""
        if hvac_mode == HVACMode.OFF:
            await self.coordinator.async_write_coil(COIL_UNIT_OFF, True)
            return
        if (mode := _HVAC_TO_MODE.get(hvac_mode)) is not None:
            await self.coordinator.async_write_register(REG_WORKING_MODE, mode)
        if not self._is_unit_on:
            await self.coordinator.async_write_coil(COIL_UNIT_ON, True)

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        """Set the power mode (HR[6465]) from a preset."""
        if (raw := _PRESET_TO_MODE.get(preset_mode)) is not None:
            await self.coordinator.async_write_register(REG_POWER_MODE, raw)
