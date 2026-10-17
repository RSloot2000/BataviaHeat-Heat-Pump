"""Diagnostics snapshots for the BataviaHeat R290 integration.

Discovered automatically by Home Assistant when this module is present in the
integration package — no manifest entry or registration is required. Both
functions return plain dicts that HA serialises to ``<domain>-<entry_id>.json``.

Credentials are redacted before they leave the machine: the cloud username and
the MD5 password hash are replaced with "***REDACTED***".
"""
from __future__ import annotations

from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import Device
from homeassistant.helpers.entity_registry import RegistryEntry
from homeassistant.util.json import async_redact_data

from .const import (
    CONF_CLOUD_PASSWORD_HASH,
    CONF_CLOUD_USERNAME,
    CONF_CONNECTION_TYPE,
    DOMAIN,
)

# Config-entry keys whose values must never be written to the diagnostics file.
_REDACT_KEYS = {CONF_CLOUD_USERNAME, CONF_CLOUD_PASSWORD_HASH}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, config_entry: ConfigEntry
) -> dict[str, Any]:
    """Return diagnostic information for a config entry.

    No secrets are exposed. The coordinator section reports health/uptime
    metadata plus per-bucket register counts from the last poll; the full data
    snapshot follows so a support engineer can see exactly what the integration
    was last reading.
    """
    coordinator = hass.data[DOMAIN][config_entry.entry_id]

    # Per-bucket register counts straight from the last poll result.
    data: dict[str, Any] = coordinator.data or {}
    bucket_counts = {
        bucket: len(values) if isinstance(values, dict) else 0
        for bucket, values in data.items()
    }

    return {
        "config_entry": async_redact_data(
            {
                "entry_id": config_entry.entry_id,
                "domain": config_entry.domain,
                "title": config_entry.title,
                "version": config_entry.version,
                "state": str(config_entry.state),
                "data": config_entry.data,
                "options": config_entry.options,
            },
            _REDACT_KEYS,
        ),
        "coordinator": {
            "connection_type": config_entry.data.get(CONF_CONNECTION_TYPE),
            "last_update_success": getattr(coordinator, "last_update_success", None),
            "last_update_time": (
                coordinator.last_update_time.isoformat()
                if coordinator.last_update_time
                else None
            ),
            "next_update_time": (
                coordinator.next_update_time.isoformat()
                if coordinator.next_update_time
                else None
            ),
            "update_count": getattr(coordinator, "update_count", None),
            "last_update_error": getattr(coordinator, "last_update_error", None),
            "register_counts": bucket_counts,
            "data": data,
        },
    }


async def async_get_device_diagnostics(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    device: Device | None,
    entity: RegistryEntry | None = None,
) -> dict[str, Any]:
    """Return diagnostics for a device, plus its optional entity."""
    diagnostics = await async_get_config_entry_diagnostics(hass, config_entry)

    diagnostics["device"] = {
        "name": device.name_sensible if device else None,
        "identifiers": sorted(map(list, device.identifiers)) if device else None,
        "model": device.model,
        "manufacturer": device.manufacturer,
        "sw_version": device.sw_version,
    }

    if entity is not None:
        diagnostics["entity"] = {
            "name": entity.name,
            "unique_id": entity.unique_id,
            "platform": entity.platform,
            "entity_id": entity.entity_id,
        }

    return diagnostics
