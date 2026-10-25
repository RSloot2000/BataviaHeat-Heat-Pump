"""Select platform for BataviaHeat R290."""
from __future__ import annotations

import logging

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import CLOUD_REGISTERS, DOMAIN, HOLDING_REGISTERS
from .coordinator import BataviaHeatCoordinator
from .entity import BataviaHeatEntity

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up BataviaHeat select entities."""
    coordinator: BataviaHeatCoordinator = hass.data[DOMAIN][entry.entry_id]
    entities: list[BataviaHeatSelect] = []

    for addr, reg_info in HOLDING_REGISTERS.items():
        if reg_info.get("entity_type") == "select":
            entities.append(BataviaHeatSelect(coordinator, addr, reg_info))

    # Cloud select entities (enums writable via cloud API)
    from .const import CONNECTION_CLOUD
    entry = coordinator.config_entry
    if entry.data.get("connection_type") == CONNECTION_CLOUD:
        modbus_enabled = entry.data.get("modbus_enabled", False)
        for addr, reg_info in CLOUD_REGISTERS.items():
            if reg_info.get("entity_type") != "select":
                continue
            if not reg_info.get("cloud_unique", True) and modbus_enabled:
                continue
            entities.append(BataviaHeatSelect(coordinator, addr, reg_info, cloud=True))

    async_add_entities(entities)


class BataviaHeatSelect(BataviaHeatEntity, SelectEntity):
    """Representation of a BataviaHeat select entity (enum parameter)."""

    def __init__(
        self,
        coordinator: BataviaHeatCoordinator,
        address: int,
        reg_info: dict,
        cloud: bool = False,
    ) -> None:
        """Initialize the select entity."""
        reg_type = "cloud" if cloud else "holding"
        super().__init__(coordinator, reg_type, address, reg_info)
        self._cloud = cloud

        # options dict: {raw_value: label_key, ...}. Default to empty so a
        # register without an "options" entry (e.g. cloud_light_strip) doesn't
        # crash entity setup with a KeyError.
        self._options_map: dict[int, str] = reg_info.get("options", {})
        self._reverse_map: dict[str, int] = {v: k for k, v in self._options_map.items()}
        self._attr_options = list(self._options_map.values())

    @property
    def current_option(self) -> str | None:
        """Return the currently selected option."""
        if self.coordinator.data is None:
            return None
        bucket = "cloud" if self._cloud else "holding"
        raw = self.coordinator.data.get(bucket, {}).get(self._address)
        if raw is None:
            return None
        return self._options_map.get(int(raw))

    async def async_select_option(self, option: str) -> None:
        """Write the selected option."""
        raw = self._reverse_map.get(option)
        if raw is None:
            return
        if self._cloud:
            await self.coordinator.async_cloud_set_value(self._address, raw)
        else:
            await self.coordinator.async_write_register(self._address, raw)
