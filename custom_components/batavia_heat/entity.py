"""Base entity for BataviaHeat R290."""
from __future__ import annotations

from homeassistant.core import callback
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, MANUFACTURER, MODEL
from .coordinator import BataviaHeatCoordinator


class BataviaHeatEntity(CoordinatorEntity[BataviaHeatCoordinator]):
    """Base class for BataviaHeat entities."""

    _attr_has_entity_name = True

    # Auto-hide: when this entity's register is absent from *successful* polls
    # for a sustained period, the device does not expose that sensor (e.g. a
    # DHW tank on a unit without one). Such entities are hidden in the entity
    # registry and automatically un-hidden when their data returns. Control
    # entities without a data-backed address (switches, the climate entity)
    # opt out by setting this to False.
    _auto_hide_when_missing: bool = True

    # Consecutive successful polls without a value before hiding. At the cloud
    # scan interval (30 s) this is ~15 min; on Modbus (10 s) it is ~5 min.
    _hide_after_misses: int = 30

    def __init__(
        self,
        coordinator: BataviaHeatCoordinator,
        reg_type: str,
        address: int,
        reg_info: dict,
    ) -> None:
        """Initialize the entity."""
        super().__init__(coordinator)
        self._reg_type = reg_type
        self._address = address
        self._reg_info = reg_info
        self._missing_count = 0

        name = reg_info.get("name", f"{reg_type}_{address}")
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_{reg_type}_{address}"
        self._attr_translation_key = name

        # Set icon if specified
        if icon := reg_info.get("icon"):
            self._attr_icon = icon

    @property
    def device_info(self) -> DeviceInfo:
        """Return device info."""
        return DeviceInfo(
            identifiers={(DOMAIN, self.coordinator.config_entry.entry_id)},
            name="BataviaHeat R290",
            manufacturer=MANUFACTURER,
            model=MODEL,
        )

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return (
            super().available
            and self.coordinator.data is not None
            and self._address in self.coordinator.data.get(self._reg_type, {})
        )

    def _has_register_value(self) -> bool:
        """Return True if this entity's register is present in the current data."""
        data = self.coordinator.data
        return bool(data and self._address in data.get(self._reg_type, {}))

    def _set_registry_hidden(self, hidden: bool) -> None:
        """Hide or un-hide this entity in the registry, respecting user choices."""
        if self.hass is None or not self.entity_id:
            return
        registry = er.async_get(self.hass)
        entry = registry.async_get(self.entity_id)
        if entry is None:
            return
        if hidden:
            # Only hide entities the user has not explicitly made visible/hidden.
            if entry.hidden_by is None:
                registry.async_update_entity(
                    self.entity_id, hidden_by=er.RegistryEntryHider.INTEGRATION
                )
        elif entry.hidden_by == er.RegistryEntryHider.INTEGRATION:
            # Only un-hide entities that we hid ourselves.
            registry.async_update_entity(self.entity_id, hidden_by=None)

    @callback
    def _handle_coordinator_update(self) -> None:
        """Manage auto-hide state, then propagate the update."""
        if self._auto_hide_when_missing and self.coordinator.last_update_success:
            # Only count misses on successful polls so a connection outage
            # (everything temporarily unavailable) never hides entities.
            if self._has_register_value():
                self._missing_count = 0
                self._set_registry_hidden(False)
            else:
                self._missing_count += 1
                if self._missing_count >= self._hide_after_misses:
                    self._set_registry_hidden(True)
        super()._handle_coordinator_update()
