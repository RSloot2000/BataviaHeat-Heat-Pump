"""Config flow for BataviaHeat R290 integration."""
from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry, ConfigFlow, ConfigFlowResult, OptionsFlow
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.selector import (
    EntitySelector,
    EntitySelectorConfig,
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    SelectOptionDict,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
)

from .cloud_client import BataviaCloudGateway, CloudAuthError
from .const import (
    CONF_BAUDRATE,
    CONF_CLOUD_DEVICE_CODE,
    CONF_CLOUD_DEVICE_NAME,
    CONF_CLOUD_PASSWORD_HASH,
    CONF_CLOUD_USERNAME,
    CONF_CONNECTION_TYPE,
    CONF_ENERGY_ENTITY,
    CONF_HOST,
    CONF_MODBUS_CONNECTION_TYPE,
    CONF_MODBUS_ENABLED,
    CONF_OFFLOAD_DB_MAX_MB,
    CONF_OFFLOAD_ENABLED,
    CONF_OFFLOAD_URL,
    CONF_SERIAL_PORT,
    CONF_SLAVE_ID,
    CONF_TCP_PORT,
    CONNECTION_CLOUD,
    CONNECTION_ESP32,
    CONNECTION_SERIAL,
    CONNECTION_TCP,
    DEFAULT_BAUDRATE,
    DEFAULT_OFFLOAD_DB_MAX_MB,
    DEFAULT_SLAVE_ID,
    DEFAULT_TCP_PORT,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)

_CONF_PENDING_MODBUS_TYPE = "_pending_modbus_type"


async def validate_tcp_connection(hass: HomeAssistant, data: dict[str, Any]) -> None:
    """Validate TCP connection to the heat pump."""
    from pymodbus.client import ModbusTcpClient

    def _test() -> None:
        port = int(data[CONF_TCP_PORT])
        slave = int(data[CONF_SLAVE_ID])
        client = ModbusTcpClient(host=data[CONF_HOST], port=port, timeout=5)
        try:
            if not client.connect():
                raise ConnectionError("Cannot connect to host")
            result = client.read_holding_registers(22, count=1, device_id=slave)
            if result.isError():
                raise ConnectionError("No Modbus response from device")
        finally:
            client.close()

    await hass.async_add_executor_job(_test)


async def validate_serial_connection(hass: HomeAssistant, data: dict[str, Any]) -> None:
    """Validate serial (RTU) connection to the heat pump."""
    from pymodbus.client import ModbusSerialClient

    def _test() -> None:
        slave = int(data[CONF_SLAVE_ID])
        baudrate = int(data[CONF_BAUDRATE])
        client = ModbusSerialClient(
            port=data[CONF_SERIAL_PORT],
            baudrate=baudrate,
            stopbits=1,
            bytesize=8,
            parity="N",
            timeout=5,
        )
        try:
            if not client.connect():
                raise ConnectionError("Cannot open serial port")
            result = client.read_holding_registers(22, count=1, device_id=slave)
            if result.isError():
                raise ConnectionError("No Modbus response from device")
        finally:
            client.close()

    await hass.async_add_executor_job(_test)


class BataviaHeatConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for BataviaHeat R290."""

    VERSION = 1

    def __init__(self) -> None:
        self._connection_type: str = CONNECTION_TCP
        self._entry_data: dict[str, Any] = {}
        self._entry_title: str = ""
        self._cloud_devices: list[dict[str, Any]] = []

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> BataviaHeatOptionsFlow:
        return BataviaHeatOptionsFlow(config_entry)

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Step 1: Choose primary connection type."""
        if user_input is not None:
            chosen = user_input[CONF_CONNECTION_TYPE]
            if chosen == CONNECTION_CLOUD:
                self._connection_type = CONNECTION_CLOUD
                return await self.async_step_cloud_login()
            self._connection_type = chosen
            if chosen == CONNECTION_SERIAL:
                return await self.async_step_serial()
            if chosen == CONNECTION_ESP32:
                return await self.async_step_esp32()
            return await self.async_step_tcp()

        data_schema = vol.Schema(
            {
                vol.Required(CONF_CONNECTION_TYPE, default=CONNECTION_TCP): SelectSelector(
                    SelectSelectorConfig(
                        options=[
                            SelectOptionDict(value=CONNECTION_CLOUD, label="Cloud (EcoHome app account)"),
                            SelectOptionDict(value=CONNECTION_TCP, label="DR164 gateway (Modbus TCP)"),
                            SelectOptionDict(value=CONNECTION_ESP32, label="ESP32 proxy (Modbus TCP)"),
                            SelectOptionDict(value=CONNECTION_SERIAL, label="Modbus RTU (Serial)"),
                        ],
                    )
                ),
            }
        )
        return self.async_show_form(step_id="user", data_schema=data_schema)

    async def async_step_cloud_login(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Authenticate against the cloud and discover devices."""
        errors: dict[str, str] = {}

        if user_input is not None:
            username: str = user_input["username"].strip()
            password: str = user_input["password"]
            password_hash = BataviaCloudGateway.hash_password(password)

            gateway = BataviaCloudGateway(self.hass, username, password_hash)
            try:
                await gateway.authenticate()
                self._cloud_devices = await gateway.fetch_devices()
            except CloudAuthError:
                errors["base"] = "invalid_auth"
            except Exception:
                _LOGGER.exception("Cloud login failed")
                errors["base"] = "cannot_connect"
            else:
                if not self._cloud_devices:
                    errors["base"] = "no_devices"
                else:
                    self._entry_data[CONF_CLOUD_USERNAME] = username
                    self._entry_data[CONF_CLOUD_PASSWORD_HASH] = password_hash
                    if len(self._cloud_devices) == 1:
                        dev = self._cloud_devices[0]
                        self._entry_data[CONF_CLOUD_DEVICE_CODE] = dev["device_code"]
                        self._entry_data[CONF_CLOUD_DEVICE_NAME] = (
                            dev.get("device_nick_name") or dev.get("device_name") or dev["device_code"]
                        )
                        return await self.async_step_cloud_modbus()
                    return await self.async_step_cloud_device()

        data_schema = vol.Schema(
            {
                vol.Required("username"): str,
                vol.Required("password"): str,
            }
        )
        return self.async_show_form(
            step_id="cloud_login", data_schema=data_schema, errors=errors
        )

    async def async_step_cloud_device(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Select one device when multiple are present on the account."""
        if user_input is not None:
            code = user_input["device_code"]
            name = next(
                (
                    d.get("device_nick_name") or d.get("device_name") or code
                    for d in self._cloud_devices
                    if d["device_code"] == code
                ),
                code,
            )
            self._entry_data[CONF_CLOUD_DEVICE_CODE] = code
            self._entry_data[CONF_CLOUD_DEVICE_NAME] = name
            return await self.async_step_cloud_modbus()

        options = [
            SelectOptionDict(
                value=d["device_code"],
                label=d.get("device_nick_name") or d.get("device_name") or d["device_code"],
            )
            for d in self._cloud_devices
        ]
        data_schema = vol.Schema(
            {vol.Required("device_code"): SelectSelector(SelectSelectorConfig(options=options))}
        )
        return self.async_show_form(step_id="cloud_device", data_schema=data_schema)

    async def async_step_cloud_modbus(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Offer to add a local Modbus connection as backup / extension."""
        if user_input is not None:
            if user_input.get("add_modbus", False):
                return await self.async_step_modbus_type()
            device_name = self._entry_data.get(CONF_CLOUD_DEVICE_NAME, "BataviaHeat")
            self._entry_title = f"BataviaHeat ({device_name})"
            self._entry_data[CONF_CONNECTION_TYPE] = CONNECTION_CLOUD
            self._entry_data[CONF_MODBUS_ENABLED] = False
            await self.async_set_unique_id(
                f"cloud_{self._entry_data[CONF_CLOUD_DEVICE_CODE]}"
            )
            self._abort_if_unique_id_configured()
            return await self.async_step_advanced()

        data_schema = vol.Schema({vol.Required("add_modbus", default=False): bool})
        return self.async_show_form(step_id="cloud_modbus", data_schema=data_schema)

    async def async_step_modbus_type(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Choose Modbus transport when adding it as cloud backup."""
        if user_input is not None:
            modbus_type = user_input[CONF_MODBUS_CONNECTION_TYPE]
            self._entry_data[_CONF_PENDING_MODBUS_TYPE] = modbus_type
            if modbus_type == CONNECTION_SERIAL:
                return await self.async_step_serial()
            if modbus_type == CONNECTION_ESP32:
                return await self.async_step_esp32()
            return await self.async_step_tcp()

        data_schema = vol.Schema(
            {
                vol.Required(CONF_MODBUS_CONNECTION_TYPE, default=CONNECTION_TCP): SelectSelector(
                    SelectSelectorConfig(
                        options=[
                            SelectOptionDict(value=CONNECTION_TCP, label="DR164 gateway (Modbus TCP)"),
                            SelectOptionDict(value=CONNECTION_ESP32, label="ESP32 proxy (Modbus TCP)"),
                            SelectOptionDict(value=CONNECTION_SERIAL, label="Modbus RTU (Serial)"),
                        ],
                    )
                ),
            }
        )
        return self.async_show_form(step_id="modbus_type", data_schema=data_schema)

    def _is_cloud_backup(self) -> bool:
        return self._connection_type == CONNECTION_CLOUD

    async def async_step_tcp(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Configure DR164 / TCP connection (primary or cloud backup)."""
        errors: dict[str, str] = {}

        if user_input is not None:
            user_input[CONF_TCP_PORT] = int(user_input[CONF_TCP_PORT])
            user_input[CONF_SLAVE_ID] = int(user_input[CONF_SLAVE_ID])
            try:
                await validate_tcp_connection(self.hass, user_input)
            except ConnectionError:
                errors["base"] = "cannot_connect"
            except Exception:
                _LOGGER.exception("Unexpected exception during TCP setup")
                errors["base"] = "unknown"
            else:
                if self._is_cloud_backup():
                    self._entry_data.update(user_input)
                    self._entry_data[CONF_CONNECTION_TYPE] = CONNECTION_CLOUD
                    self._entry_data[CONF_MODBUS_ENABLED] = True
                    self._entry_data[CONF_MODBUS_CONNECTION_TYPE] = (
                        self._entry_data.pop(_CONF_PENDING_MODBUS_TYPE, CONNECTION_TCP)
                    )
                    device_name = self._entry_data.get(CONF_CLOUD_DEVICE_NAME, "BataviaHeat")
                    self._entry_title = f"BataviaHeat ({device_name} + DR164)"
                    await self.async_set_unique_id(
                        f"cloud_{self._entry_data[CONF_CLOUD_DEVICE_CODE]}_tcp_{user_input[CONF_HOST]}"
                    )
                else:
                    self._entry_data = {CONF_CONNECTION_TYPE: CONNECTION_TCP, **user_input}
                    self._entry_title = (
                        f"BataviaHeat R290 ({user_input[CONF_HOST]}:{user_input[CONF_TCP_PORT]})"
                    )
                    await self.async_set_unique_id(
                        f"tcp_{user_input[CONF_HOST]}:{user_input[CONF_TCP_PORT]}_{user_input[CONF_SLAVE_ID]}"
                    )
                self._abort_if_unique_id_configured()
                return await self.async_step_advanced()

        data_schema = vol.Schema(
            {
                vol.Required(CONF_HOST): str,
                vol.Required(CONF_TCP_PORT, default=DEFAULT_TCP_PORT): NumberSelector(
                    NumberSelectorConfig(min=1, max=65535, step=1, mode=NumberSelectorMode.BOX)
                ),
                vol.Required(CONF_SLAVE_ID, default=DEFAULT_SLAVE_ID): NumberSelector(
                    NumberSelectorConfig(min=1, max=247, step=1, mode=NumberSelectorMode.BOX)
                ),
            }
        )
        return self.async_show_form(step_id="tcp", data_schema=data_schema, errors=errors)

    async def async_step_esp32(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Configure ESP32 proxy / TCP connection (primary or cloud backup)."""
        errors: dict[str, str] = {}

        if user_input is not None:
            user_input[CONF_TCP_PORT] = int(user_input[CONF_TCP_PORT])
            user_input[CONF_SLAVE_ID] = int(user_input[CONF_SLAVE_ID])
            try:
                await validate_tcp_connection(self.hass, user_input)
            except ConnectionError:
                errors["base"] = "cannot_connect"
            except Exception:
                _LOGGER.exception("Unexpected exception during ESP32 setup")
                errors["base"] = "unknown"
            else:
                if self._is_cloud_backup():
                    self._entry_data.update(user_input)
                    self._entry_data[CONF_CONNECTION_TYPE] = CONNECTION_CLOUD
                    self._entry_data[CONF_MODBUS_ENABLED] = True
                    self._entry_data[CONF_MODBUS_CONNECTION_TYPE] = (
                        self._entry_data.pop(_CONF_PENDING_MODBUS_TYPE, CONNECTION_ESP32)
                    )
                    device_name = self._entry_data.get(CONF_CLOUD_DEVICE_NAME, "BataviaHeat")
                    self._entry_title = f"BataviaHeat ({device_name} + ESP32)"
                    await self.async_set_unique_id(
                        f"cloud_{self._entry_data[CONF_CLOUD_DEVICE_CODE]}_esp32_{user_input[CONF_HOST]}"
                    )
                else:
                    self._entry_data = {CONF_CONNECTION_TYPE: CONNECTION_ESP32, **user_input}
                    self._entry_title = f"BataviaHeat R290 ESP32 ({user_input[CONF_HOST]})"
                    await self.async_set_unique_id(
                        f"esp32_{user_input[CONF_HOST]}:{user_input[CONF_TCP_PORT]}_{user_input[CONF_SLAVE_ID]}"
                    )
                self._abort_if_unique_id_configured()
                return await self.async_step_advanced()

        data_schema = vol.Schema(
            {
                vol.Required(CONF_HOST): str,
                vol.Required(CONF_TCP_PORT, default=DEFAULT_TCP_PORT): NumberSelector(
                    NumberSelectorConfig(min=1, max=65535, step=1, mode=NumberSelectorMode.BOX)
                ),
                vol.Required(CONF_SLAVE_ID, default=DEFAULT_SLAVE_ID): NumberSelector(
                    NumberSelectorConfig(min=1, max=247, step=1, mode=NumberSelectorMode.BOX)
                ),
            }
        )
        return self.async_show_form(step_id="esp32", data_schema=data_schema, errors=errors)

    async def async_step_serial(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Configure serial RTU connection (primary or cloud backup)."""
        errors: dict[str, str] = {}

        if user_input is not None:
            user_input.setdefault(CONF_BAUDRATE, DEFAULT_BAUDRATE)
            user_input[CONF_SLAVE_ID] = int(user_input[CONF_SLAVE_ID])
            user_input[CONF_BAUDRATE] = int(user_input[CONF_BAUDRATE])
            try:
                await validate_serial_connection(self.hass, user_input)
            except ConnectionError:
                errors["base"] = "cannot_connect"
            except Exception:
                _LOGGER.exception("Unexpected exception during serial setup")
                errors["base"] = "unknown"
            else:
                if self._is_cloud_backup():
                    self._entry_data.update(user_input)
                    self._entry_data[CONF_CONNECTION_TYPE] = CONNECTION_CLOUD
                    self._entry_data[CONF_MODBUS_ENABLED] = True
                    self._entry_data[CONF_MODBUS_CONNECTION_TYPE] = (
                        self._entry_data.pop(_CONF_PENDING_MODBUS_TYPE, CONNECTION_SERIAL)
                    )
                    device_name = self._entry_data.get(CONF_CLOUD_DEVICE_NAME, "BataviaHeat")
                    self._entry_title = f"BataviaHeat ({device_name} + Serial)"
                    await self.async_set_unique_id(
                        f"cloud_{self._entry_data[CONF_CLOUD_DEVICE_CODE]}_serial_{user_input[CONF_SERIAL_PORT]}"
                    )
                else:
                    self._entry_data = {CONF_CONNECTION_TYPE: CONNECTION_SERIAL, **user_input}
                    self._entry_title = f"BataviaHeat R290 ({user_input[CONF_SERIAL_PORT]})"
                    await self.async_set_unique_id(
                        f"serial_{user_input[CONF_SERIAL_PORT]}_{user_input[CONF_SLAVE_ID]}"
                    )
                self._abort_if_unique_id_configured()
                return await self.async_step_advanced()

        data_schema = vol.Schema(
            {
                vol.Required(CONF_SERIAL_PORT): str,
                vol.Required(CONF_SLAVE_ID, default=DEFAULT_SLAVE_ID): NumberSelector(
                    NumberSelectorConfig(min=1, max=247, step=1, mode=NumberSelectorMode.BOX)
                ),
                vol.Optional(CONF_BAUDRATE, default=DEFAULT_BAUDRATE): NumberSelector(
                    NumberSelectorConfig(min=1200, max=115200, step=1, mode=NumberSelectorMode.BOX)
                ),
            }
        )
        return self.async_show_form(step_id="serial", data_schema=data_schema, errors=errors)

    async def async_step_advanced(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Optional energy meter + register offload settings."""
        if user_input is not None:
            return self.async_create_entry(
                title=self._entry_title,
                data=self._entry_data,
                options=_normalize_advanced_options(user_input),
            )

        dir_options = await self.hass.async_add_executor_job(_discover_offload_dirs)
        schema = _build_advanced_schema(
            energy_entity="",
            offload_enabled=False,
            offload_url="",
            offload_db_max_mb=DEFAULT_OFFLOAD_DB_MAX_MB,
            dir_options=dir_options,
        )
        return self.async_show_form(step_id="advanced", data_schema=schema)


class BataviaHeatOptionsFlow(OptionsFlow):
    """Handle options flow for BataviaHeat R290."""

    def __init__(self, config_entry: ConfigEntry) -> None:
        self._config_entry = config_entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        if user_input is not None:
            return self.async_create_entry(data=_normalize_advanced_options(user_input))

        dir_options = await self.hass.async_add_executor_job(_discover_offload_dirs)
        schema = _build_advanced_schema(
            energy_entity=self._config_entry.options.get(CONF_ENERGY_ENTITY, ""),
            offload_enabled=self._config_entry.options.get(CONF_OFFLOAD_ENABLED, False),
            offload_url=self._config_entry.options.get(CONF_OFFLOAD_URL, ""),
            offload_db_max_mb=self._config_entry.options.get(
                CONF_OFFLOAD_DB_MAX_MB, DEFAULT_OFFLOAD_DB_MAX_MB
            ),
            dir_options=dir_options,
        )
        return self.async_show_form(step_id="init", data_schema=schema)


def _build_advanced_schema(
    energy_entity: str,
    offload_enabled: bool,
    offload_url: str,
    offload_db_max_mb: float,
    dir_options: list[str],
) -> vol.Schema:
    if offload_url and offload_url not in dir_options:
        dir_options.append(offload_url)
    return vol.Schema(
        {
            vol.Optional(
                CONF_ENERGY_ENTITY,
                description={"suggested_value": energy_entity} if energy_entity else {},
            ): EntitySelector(EntitySelectorConfig(domain="sensor", device_class="energy")),
            vol.Optional(CONF_OFFLOAD_ENABLED, default=offload_enabled): bool,
            vol.Optional(
                CONF_OFFLOAD_URL,
                description={"suggested_value": offload_url} if offload_url else {},
            ): SelectSelector(
                SelectSelectorConfig(
                    options=[SelectOptionDict(value=d, label=d) for d in dir_options],
                    mode=SelectSelectorMode.DROPDOWN,
                    custom_value=True,
                )
            ),
            vol.Optional(CONF_OFFLOAD_DB_MAX_MB, default=offload_db_max_mb): NumberSelector(
                NumberSelectorConfig(
                    min=0, max=1024000, step=1,
                    mode=NumberSelectorMode.BOX,
                    unit_of_measurement="MB",
                )
            ),
        }
    )


def _normalize_advanced_options(user_input: dict[str, Any]) -> dict[str, Any]:
    options = dict(user_input)
    options.setdefault(CONF_ENERGY_ENTITY, "")
    options.setdefault(CONF_OFFLOAD_URL, "")
    options.setdefault(CONF_OFFLOAD_ENABLED, False)
    options.setdefault(CONF_OFFLOAD_DB_MAX_MB, DEFAULT_OFFLOAD_DB_MAX_MB)
    return options


def _discover_offload_dirs() -> list[str]:
    import os
    from pathlib import Path

    roots = [Path("/share"), Path("/media"), Path("/config")]
    dirs: list[str] = []
    for root in roots:
        if root.is_dir():
            dirs.append(str(root))
            try:
                for child in sorted(root.iterdir()):
                    if child.is_dir() and os.access(child, os.W_OK):
                        dirs.append(str(child))
            except PermissionError:
                pass
    return dirs