"""Switch platform for BataviaHeat R290."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity

from .const import COILS, DOMAIN
from .coordinator import BataviaHeatCoordinator
from .entity import BataviaHeatEntity

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up BataviaHeat switch entities."""
    coordinator: BataviaHeatCoordinator = hass.data[DOMAIN][entry.entry_id]
    entities: dict[int, BataviaHeatSwitch] = {}

    for addr, reg_info in COILS.items():
        if reg_info.get("entity_type") == "switch":
            entities[addr] = BataviaHeatSwitch(coordinator, addr, reg_info)

    # Wire up parent dependencies (e.g. silent_level_2 depends on silent_mode)
    for addr, entity in entities.items():
        if parent_addr := COILS[addr].get("requires"):
            entity.set_parent(entities[parent_addr])

    async_add_entities(entities.values())


class BataviaHeatSwitch(RestoreEntity, BataviaHeatEntity, SwitchEntity):
    """Representation of a BataviaHeat pulse-coil switch.

    BataviaHeat uses separate coils for ON and OFF (fire-and-forget pulses).
    There is no readable coil state — state is determined by:
      1. state_register: a holding register that reflects hardware state (e.g. HR[768])
      2. RestoreEntity: persists assumed state across HA restarts (fallback)
    """

    _attr_assumed_state = True
    # Coils have no data-backed register in coordinator.data — never auto-hide.
    _auto_hide_when_missing = False

    def __init__(
        self,
        coordinator: BataviaHeatCoordinator,
        address: int,
        reg_info: dict,
    ) -> None:
        """Initialize the switch."""
        super().__init__(coordinator, "coil", address, reg_info)
        self._on_coil = reg_info["on_coil"]
        self._off_coil = reg_info["off_coil"]
        self._is_on: bool | None = None
        self._parent: BataviaHeatSwitch | None = None

        # Optional: holding register that reflects the actual hardware state
        # e.g. HR[768] operational_status > 0 means unit is ON
        self._state_register: tuple[str, int] | None = None
        if sr := reg_info.get("state_register"):
            self._state_register = (sr["type"], sr["address"])

    def set_parent(self, parent: BataviaHeatSwitch) -> None:
        """Set a parent switch that must be ON for this switch to be available."""
        self._parent = parent

    @property
    def available(self) -> bool:
        """Available when coordinator is connected and parent (if any) is ON."""
        if not self.coordinator.last_update_success:
            return False
        if self._parent is not None and self._parent.is_on is False:
            return False
        return True

    @property
    def is_on(self) -> bool | None:
        """Return switch state from hardware register or assumed state."""
        if self._state_register and self.coordinator.data:
            reg_type, addr = self._state_register
            val = self.coordinator.data.get(reg_type, {}).get(addr)
            if val is not None:
                return val > 0
        return self._is_on

    async def async_added_to_hass(self) -> None:
        """Restore previous state on startup."""
        await super().async_added_to_hass()
        if self._state_register is None:
            # No hardware register — restore last known state
            if (last_state := await self.async_get_last_state()) is not None:
                if last_state.state == "on":
                    self._is_on = True
                elif last_state.state == "off":
                    self._is_on = False

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the switch on by writing the ON coil."""
        await self.coordinator.async_write_coil(self._on_coil, True)
        self._is_on = True
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the switch off by writing the OFF coil."""
        await self.coordinator.async_write_coil(self._off_coil, True)
        self._is_on = False
        self.async_write_ha_state()
