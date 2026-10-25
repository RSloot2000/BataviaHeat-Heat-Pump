"""Binary sensor platform for BataviaHeat R290."""
from __future__ import annotations

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DISCRETE_INPUTS, DOMAIN, HOLDING_REGISTERS
from .coordinator import BataviaHeatCoordinator
from .entity import BataviaHeatEntity

DEVICE_CLASS_MAP = {
    "running": BinarySensorDeviceClass.RUNNING,
    "problem": BinarySensorDeviceClass.PROBLEM,
    "heat": BinarySensorDeviceClass.HEAT,
    "cold": BinarySensorDeviceClass.COLD,
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up BataviaHeat binary sensor entities."""
    coordinator: BataviaHeatCoordinator = hass.data[DOMAIN][entry.entry_id]
    entities: list[BataviaHeatBinarySensor] = []

    for addr, reg_info in DISCRETE_INPUTS.items():
        if reg_info.get("entity_type") == "binary_sensor":
            if not coordinator._is_address_read("discrete", addr):
                continue
            entities.append(
                BataviaHeatBinarySensor(coordinator, "discrete", addr, reg_info)
            )

    # Binary sensors from holding registers (e.g. compressor ON/OFF)
    for addr, reg_info in HOLDING_REGISTERS.items():
        if reg_info.get("entity_type") == "binary_sensor":
            if not coordinator._is_address_read("holding", addr):
                continue
            entities.append(
                BataviaHeatBinarySensor(coordinator, "holding", addr, reg_info)
            )

    async_add_entities(entities)


class BataviaHeatBinarySensor(BataviaHeatEntity, BinarySensorEntity):
    """Representation of a BataviaHeat binary sensor."""

    def __init__(
        self,
        coordinator: BataviaHeatCoordinator,
        reg_type: str,
        address: int,
        reg_info: dict,
    ) -> None:
        """Initialize the binary sensor."""
        super().__init__(coordinator, reg_type, address, reg_info)

        if dc := reg_info.get("device_class"):
            self._attr_device_class = DEVICE_CLASS_MAP.get(dc)

    @property
    def is_on(self) -> bool | None:
        """Return the state of the binary sensor."""
        if self.coordinator.data is None:
            return None
        val = self.coordinator.data.get(self._reg_type, {}).get(self._address)
        if val is None:
            return None
        return bool(val)
