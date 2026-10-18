"""The BataviaHeat R290 integration."""
from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers.event import async_track_time_interval

from .const import DOMAIN
from .coordinator import CONSOLIDATE_INTERVAL, BataviaHeatCoordinator

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [
    Platform.SENSOR,
    Platform.BINARY_SENSOR,
    Platform.SWITCH,
    Platform.NUMBER,
    Platform.SELECT,
    Platform.CLIMATE,
]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up BataviaHeat R290 from a config entry."""
    coordinator = BataviaHeatCoordinator(hass, entry)
    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(_async_update_options))

    # Always consolidate offloaded snap_*.json files into snapshots.db on a
    # fixed schedule (and once now). No-op when offload isn't to a local path.
    entry.async_on_unload(
        async_track_time_interval(
            hass, coordinator.async_consolidate_snapshots, CONSOLIDATE_INTERVAL,
        )
    )
    entry.async_create_background_task(
        hass,
        coordinator.async_consolidate_snapshots(),
        name="batavia_heat_consolidate_startup",
    )

    # Register integration services once, regardless of how many entries exist.
    _async_register_services(hass)
    return True


def _async_register_services(hass: HomeAssistant) -> None:
    """Register BataviaHeat services exactly once across all config entries."""
    if hass.services.has_service(DOMAIN, "reload"):
        return

    async def _async_reload(_call: ServiceCall) -> None:
        """Reload every BataviaHeat config entry (apply options without a restart)."""
        for entry in hass.config_entries.async_entries(DOMAIN):
            await hass.config_entries.async_reload(entry.entry_id)

    async def _async_refresh_data(_call: ServiceCall) -> None:
        """Force an immediate cloud/Modbus poll of every configured device."""
        for entry in hass.config_entries.async_entries(DOMAIN):
            coordinator = hass.data[DOMAIN].get(entry.entry_id)
            if coordinator is not None:
                hass.async_create_task(
                    coordinator.async_refresh(),
                    name=f"batavia_heat_refresh_{entry.entry_id}",
                )

    hass.services.async_register(DOMAIN, "reload", _async_reload)
    hass.services.async_register(DOMAIN, "refresh_data", _async_refresh_data)


async def _async_update_options(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload integration when options change."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        coordinator: BataviaHeatCoordinator = hass.data[DOMAIN].pop(entry.entry_id)
        await coordinator.async_close()

        # Drop the services only once the very last entry is gone, so multiple
        # entries never lose access while another still needs them.
        if not hass.config_entries.async_entries(DOMAIN):
            hass.services.async_remove(DOMAIN, "reload")
            hass.services.async_remove(DOMAIN, "refresh_data")

    return unload_ok
