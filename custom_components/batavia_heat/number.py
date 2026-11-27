"""Number platform for BataviaHeat R290."""
from __future__ import annotations

import logging

from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import CLOUD_REGISTERS, DOMAIN, HOLDING_REGISTERS
from .coordinator import BataviaHeatCoordinator
from .entity import BataviaHeatEntity

_LOGGER = logging.getLogger(__name__)

UNIT_MAP = {
    "°C": UnitOfTemperature.CELSIUS,
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up BataviaHeat number entities (setpoints)."""
    coordinator: BataviaHeatCoordinator = hass.data[DOMAIN][entry.entry_id]
    entities: list[BataviaHeatNumber] = []

    for addr, reg_info in HOLDING_REGISTERS.items():
        if reg_info.get("entity_type") == "number":
            entities.append(BataviaHeatNumber(coordinator, "holding", addr, reg_info))

    # Cloud number entities (setpoints writable via cloud API)
    from .const import CONNECTION_CLOUD
    entry = coordinator.config_entry
    if entry.data.get("connection_type") == CONNECTION_CLOUD:
        modbus_enabled = entry.data.get("modbus_enabled", False)
        for addr, reg_info in CLOUD_REGISTERS.items():
            if reg_info.get("entity_type") != "number":
                continue
            if not reg_info.get("cloud_unique", True) and modbus_enabled:
                continue
            entities.append(BataviaHeatNumber(coordinator, "cloud", addr, reg_info))

    async_add_entities(entities)


class BataviaHeatNumber(BataviaHeatEntity, NumberEntity):
    """Representation of a BataviaHeat number entity (setpoint)."""

    _attr_mode = NumberMode.BOX

    def __init__(
        self,
        coordinator: BataviaHeatCoordinator,
        reg_type: str,
        address: int,
        reg_info: dict,
    ) -> None:
        """Initialize the number entity."""
        super().__init__(coordinator, reg_type, address, reg_info)

        self._scale = reg_info.get("scale", 1)

        if unit := reg_info.get("unit"):
            self._attr_native_unit_of_measurement = UNIT_MAP.get(unit, unit)

        self._attr_native_min_value = reg_info.get("min", 0)
        self._attr_native_max_value = reg_info.get("max", 100)
        self._attr_native_step = self._scale

    @property
    def native_value(self) -> float | None:
        """Return the current value."""
        if self.coordinator.data is None:
            return None
        return self.coordinator.data.get(self._reg_type, {}).get(self._address)

    async def async_set_native_value(self, value: float) -> None:
        """Set a new value."""
        # round() not int(): float division truncates (45.0 / 0.1 == 449.999…).
        raw_value = round(value / self._scale)
        if self._reg_type == "cloud":
            await self.coordinator.async_cloud_set_value(self._address, raw_value)
        else:
            await self.coordinator.async_write_register(self._address, raw_value)
