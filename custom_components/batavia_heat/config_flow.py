"""Config flow for BataviaHeat R290 integration."""
from __future__ import annotations

import logging
from typing import Any, Mapping

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
    CONF_NUM_OUTDOOR_UNITS,
    CONF_REGISTER_MAP,
    CONF_ENERGY_ENTITY_MODULE_0,
    CONF_ENERGY_ENTITY_MODULE_1,
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
    CONNECTION_MODE_BOTH,
    CONNECTION_MODE_CLOUD,
    NUM_OUTDOOR_UNITS_SINGLE,
    NUM_OUTDOOR_UNITS_CASCADE,
    CONNECTION_MODE_MODBUS,
    CONNECTION_ESP32,
    REGISTER_MAP_BATAVIA,
    REGISTER_MAP_NEWNTIDE,
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

# Options-flow "action" chosen on the init screen: edit the current setup, or
# add the complementary transport (cloud / Modbus) to it.
CONF_INIT_ACTION = "init_action"
INIT_ACTION_EDIT = "edit"
INIT_ACTION_ADD_CLOUD = "add_cloud"
INIT_ACTION_ADD_MODBUS = "add_modbus"
# Human-readable label for each connection mode, shown on the init screen.
_MODE_LABELS = {
    CONNECTION_MODE_CLOUD: "Cloud",
    CONNECTION_MODE_MODBUS: "Modbus",
    CONNECTION_MODE_BOTH: "Cloud + Modbus",
}


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
        # Number of outdoor units ("1" single / "2" cascade). None until the
        # units step chooses, so the first advanced step can ask first.
        self._num_outdoor_units: str | None = None
        # When the user picked the "Both (Cloud + Modbus)" option, skip the
        # "add Modbus?" confirm prompt and go straight to Modbus transport setup.
        self._want_modbus: bool = False

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
            if chosen == CONNECTION_MODE_BOTH:
                # Both (Cloud + Modbus): cloud is primary and preferred, Modbus
                # runs alongside. Reuse the cloud flow, but skip the "add Modbus?"
                # confirm since the user explicitly chose both.
                self._connection_type = CONNECTION_CLOUD
                self._want_modbus = True
                return await self.async_step_cloud_login()
            if chosen == CONNECTION_CLOUD:
                self._connection_type = CONNECTION_CLOUD
                self._want_modbus = False
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
                            SelectOptionDict(value=CONNECTION_MODE_BOTH, label="Both (Cloud + Modbus)"),
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
            if self._want_modbus or user_input.get("add_modbus", False):
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

    async def async_step_units(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Choose how many outdoor units: 1 single, or 2 (cascade)."""
        if user_input is not None:
            self._num_outdoor_units = user_input[CONF_NUM_OUTDOOR_UNITS]
            return await self.async_step_advanced()

        data_schema = vol.Schema(
            {
                vol.Required(CONF_NUM_OUTDOOR_UNITS, default=NUM_OUTDOOR_UNITS_SINGLE):
                    SelectSelector(
                        SelectSelectorConfig(
                            options=[
                                SelectOptionDict(
                                    value=NUM_OUTDOOR_UNITS_SINGLE,
                                    label="1 outdoor unit",
                                ),
                                SelectOptionDict(
                                    value=NUM_OUTDOOR_UNITS_CASCADE,
                                    label="2 outdoor units (cascade)",
                                ),
                            ],
                        )
                    ),
            }
        )
        return self.async_show_form(step_id="units", data_schema=data_schema)

    async def async_step_advanced(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Optional energy meter + register offload settings."""
        # Branch: ask how many outdoor units before showing the meter fields, so
        # a single unit never sees the redundant per-cascade meter fields.
        if self._num_outdoor_units is None:
            return await self.async_step_units(user_input)

        if user_input is not None:
            return self.async_create_entry(
                title=self._entry_title,
                data=self._entry_data,
                options=_normalize_advanced_options(
                    user_input,
                    num_outdoor_units=self._num_outdoor_units,
                ),
            )

        dir_options = await self.hass.async_add_executor_job(_discover_offload_dirs)
        schema = _build_advanced_schema(
            energy_entity="",
            offload_enabled=False,
            offload_url="",
            offload_db_max_mb=DEFAULT_OFFLOAD_DB_MAX_MB,
            dir_options=dir_options,
            energy_entity_module_0="",
            energy_entity_module_1="",
            register_map=REGISTER_MAP_BATAVIA,
            num_outdoor_units=self._num_outdoor_units,
        )
        return self.async_show_form(step_id="advanced", data_schema=schema)


class BataviaHeatOptionsFlow(OptionsFlow):
    """Handle options flow for BataviaHeat R290.

    Lets a configured entry switch between Cloud-only, Modbus-only, and
    Both (Cloud + Modbus, cloud sensors preferred). Connection settings are
    written back to ``entry.data`` (the coordinator reads them); advanced
    settings (energy meter, offload, register map) go to ``entry.options``.
    """

    def __init__(self, config_entry: ConfigEntry) -> None:
        self._config_entry = config_entry
        # Pending state carried across the multi-step flow (cloud login is only
        # needed when a Modbus-only entry adds cloud credentials).
        self._mode: str = _current_mode(config_entry)
        # Number of outdoor units; default from the entry so editing an existing
        # entry keeps its cascade/single setting. "1" = single, "2" = cascade.
        self._num_outdoor_units: str = config_entry.options.get(
            CONF_NUM_OUTDOOR_UNITS, NUM_OUTDOOR_UNITS_SINGLE
        )
        self._modbus_type: str = CONNECTION_TCP
        self._modbus_details: dict[str, Any] = {}
        self._advanced_options: dict[str, Any] = {}
        self._cloud_creds: dict[str, Any] = {}
        self._cloud_devices: list[dict[str, Any]] = []

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Step 1: choose what to do — edit the current setup or add a transport.

        Lands on the entry's current configuration. A single action lets the user
        add the complementary transport (cloud or Modbus) without re-classifying
        the whole entry.
        """
        entry = self._config_entry
        self._mode = _current_mode(entry)

        if user_input is not None:
            action = user_input[CONF_INIT_ACTION]
            if action == INIT_ACTION_EDIT:
                return await self.async_step_details()
            if action == INIT_ACTION_ADD_CLOUD:
                # Adding cloud to a Modbus-only entry → result is "both".
                # Preserve the existing Modbus transport details so they are not
                # dropped when the entry becomes cloud + Modbus.
                self._modbus_type = _effective_modbus_type(entry) or CONNECTION_TCP
                self._modbus_details = {
                    k: entry.data.get(k) for k in _MODBUS_DETAIL_KEYS
                }
                return await self.async_step_cloud_login()
            if action == INIT_ACTION_ADD_MODBUS:
                # Adding Modbus to a Cloud-only entry → result is "both"; the
                # transport is chosen on the details screen.
                self._mode = CONNECTION_MODE_BOTH
                self._modbus_type = CONNECTION_TCP
                self._modbus_details = {}
                return await self.async_step_details()

        actions = [
            SelectOptionDict(
                value=INIT_ACTION_EDIT,
                label=f"Edit {_MODE_LABELS.get(self._mode, self._mode)} settings",
            )
        ]
        # Only offer to add a transport when it is absent. "Both" already has
        # both, so it only shows the edit action.
        if self._mode == CONNECTION_MODE_MODBUS:
            actions.append(
                SelectOptionDict(
                    value=INIT_ACTION_ADD_CLOUD, label="Add cloud connection"
                )
            )
        if self._mode == CONNECTION_MODE_CLOUD:
            actions.append(
                SelectOptionDict(
                    value=INIT_ACTION_ADD_MODBUS, label="Add Modbus connection"
                )
            )

        data_schema = vol.Schema(
            {
                vol.Required(CONF_INIT_ACTION, default=INIT_ACTION_EDIT): SelectSelector(
                    SelectSelectorConfig(options=actions)
                ),
            }
        )
        return self.async_show_form(step_id="init", data_schema=data_schema)

    async def async_step_details(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Step 2: Modbus transport/details (when needed) + advanced settings."""
        entry = self._config_entry

        if user_input is not None:
            self._modbus_type = user_input.get(
                CONF_MODBUS_CONNECTION_TYPE, CONNECTION_TCP
            )
            self._modbus_details = {
                CONF_HOST: user_input.get(CONF_HOST, ""),
                CONF_TCP_PORT: user_input.get(CONF_TCP_PORT, DEFAULT_TCP_PORT),
                CONF_SLAVE_ID: user_input.get(CONF_SLAVE_ID, DEFAULT_SLAVE_ID),
                CONF_SERIAL_PORT: user_input.get(CONF_SERIAL_PORT, ""),
                CONF_BAUDRATE: user_input.get(CONF_BAUDRATE, DEFAULT_BAUDRATE),
            }
            self._num_outdoor_units = user_input.get(
                CONF_NUM_OUTDOOR_UNITS, self._num_outdoor_units
            )
            self._advanced_options = _normalize_advanced_options(
                user_input, num_outdoor_units=self._num_outdoor_units
            )
            return await self._finalize(entry)

        dir_options = await self.hass.async_add_executor_job(_discover_offload_dirs)
        schema = _build_options_schema(
            entry=entry,
            mode=self._mode,
            dir_options=dir_options,
            energy_entity=entry.options.get(CONF_ENERGY_ENTITY, ""),
            offload_enabled=entry.options.get(CONF_OFFLOAD_ENABLED, False),
            offload_url=entry.options.get(CONF_OFFLOAD_URL, ""),
            offload_db_max_mb=entry.options.get(
                CONF_OFFLOAD_DB_MAX_MB, DEFAULT_OFFLOAD_DB_MAX_MB
            ),
            energy_entity_module_0=entry.options.get(
                CONF_ENERGY_ENTITY_MODULE_0, ""
            ),
            energy_entity_module_1=entry.options.get(
                CONF_ENERGY_ENTITY_MODULE_1, ""
            ),
            register_map=entry.options.get(
                CONF_REGISTER_MAP, REGISTER_MAP_BATAVIA
            ),
            num_outdoor_units=self._num_outdoor_units,
        )
        return self.async_show_form(step_id="details", data_schema=schema)

    async def async_step_cloud_login(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """One-time cloud login when a Modbus-only entry adds the cloud path."""
        errors: dict[str, str] = {}

        if user_input is not None:
            username: str = user_input["username"].strip()
            password_hash = BataviaCloudGateway.hash_password(user_input["password"])
            gateway = BataviaCloudGateway(self.hass, username, password_hash)
            try:
                await gateway.authenticate()
                devices = await gateway.fetch_devices()
            except CloudAuthError:
                errors["base"] = "invalid_auth"
            except Exception:
                _LOGGER.exception("Cloud login failed")
                errors["base"] = "cannot_connect"
            else:
                if not devices:
                    errors["base"] = "no_devices"
                elif len(devices) == 1:
                    dev = devices[0]
                    self._cloud_creds.update({
                        CONF_CLOUD_USERNAME: username,
                        CONF_CLOUD_PASSWORD_HASH: password_hash,
                        CONF_CLOUD_DEVICE_CODE: dev["device_code"],
                        CONF_CLOUD_DEVICE_NAME: (
                            dev.get("device_nick_name") or dev.get("device_name") or dev["device_code"]
                        ),
                    })
                    return await self._finalize(self._config_entry)
                self._cloud_devices = devices
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
        """Pick one device when multiple are present on the account."""
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
            self._cloud_creds.update({
                CONF_CLOUD_DEVICE_CODE: code,
                CONF_CLOUD_DEVICE_NAME: name,
            })
            return await self._finalize(self._config_entry)

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

    def _has_cloud_creds(self, entry: ConfigEntry) -> bool:
        """Return True when the entry already holds usable cloud credentials."""
        return all(
            entry.data.get(k)
            for k in (CONF_CLOUD_USERNAME, CONF_CLOUD_PASSWORD_HASH, CONF_CLOUD_DEVICE_CODE)
        )

    async def _finalize(self, entry: ConfigEntry) -> ConfigFlowResult:
        """Persist new connection settings to entry.data, advanced to entry.options."""
        mode = self._mode
        if mode == CONNECTION_MODE_CLOUD:
            new_data = _to_cloud(entry.data)
        elif mode == CONNECTION_MODE_MODBUS:
            new_data = _to_modbus(entry.data, self._modbus_type, self._modbus_details)
        else:
            new_data = _to_both(entry.data, self._modbus_type, self._modbus_details)
        # Merge freshly-entered cloud credentials from the login step, if any.
        new_data.update(self._cloud_creds)

        try:
            await self.hass.config_entries.async_update_entry(entry, data=new_data)
        except Exception as err:  # noqa: BLE001
            _LOGGER.warning("Failed to update entry connection settings: %s", err)

        return self.async_create_entry(data=self._advanced_options)


# ── Connection-mode helpers ──────────────────────────────────────────────────
# An entry's *mode* is cloud / modbus / both. "both" is stored as cloud primary
# (connection_type=cloud) with modbus_enabled=True; the coordinator already runs
# both and prefers cloud sensors, so these helpers only reshape entry.data.


def _current_mode(entry: ConfigEntry) -> str:
    """Return the entry's connection mode: cloud / modbus / both."""
    ctype = entry.data.get(CONF_CONNECTION_TYPE, CONNECTION_TCP)
    if ctype == CONNECTION_CLOUD:
        return (
            CONNECTION_MODE_BOTH
            if entry.data.get(CONF_MODBUS_ENABLED, False)
            else CONNECTION_MODE_CLOUD
        )
    return CONNECTION_MODE_MODBUS


_MODBUS_DETAIL_KEYS = (
    CONF_HOST,
    CONF_TCP_PORT,
    CONF_SLAVE_ID,
    CONF_SERIAL_PORT,
    CONF_BAUDRATE,
)


def _strip_modbus_fields(data: dict[str, Any]) -> None:
    """Drop Modbus transport details from a data dict."""
    for key in _MODBUS_DETAIL_KEYS:
        data.pop(key, None)


def _apply_modbus_details(
    data: dict[str, Any], modbus_type: str, details: Mapping[str, Any]
) -> None:
    """Store the Modbus transport + its connection details in a data dict."""
    data[CONF_MODBUS_CONNECTION_TYPE] = modbus_type
    for key in _MODBUS_DETAIL_KEYS:
        if key in details:
            data[key] = details[key]


def _to_cloud(base: Mapping[str, Any]) -> dict[str, Any]:
    """Return cloud-only connection data (Modbus disabled)."""
    data = dict(base)
    data[CONF_CONNECTION_TYPE] = CONNECTION_CLOUD
    data[CONF_MODBUS_ENABLED] = False
    _strip_modbus_fields(data)
    return data


def _to_modbus(
    base: Mapping[str, Any], modbus_type: str, details: Mapping[str, Any]
) -> dict[str, Any]:
    """Return Modbus-only connection data (cloud removed)."""
    data = dict(base)
    data[CONF_CONNECTION_TYPE] = modbus_type
    data[CONF_MODBUS_ENABLED] = False
    for key in (CONF_CLOUD_USERNAME, CONF_CLOUD_PASSWORD_HASH, CONF_CLOUD_DEVICE_CODE, CONF_CLOUD_DEVICE_NAME):
        data.pop(key, None)
    _apply_modbus_details(data, modbus_type, details)
    return data


def _to_both(
    base: Mapping[str, Any], modbus_type: str, details: Mapping[str, Any]
) -> dict[str, Any]:
    """Return cloud + Modbus connection data (cloud preferred)."""
    data = dict(base)
    data[CONF_CONNECTION_TYPE] = CONNECTION_CLOUD
    data[CONF_MODBUS_ENABLED] = True
    _apply_modbus_details(data, modbus_type, details)
    return data


def _effective_modbus_type(entry: ConfigEntry) -> str | None:
    """Return the Modbus transport whose connection details can be edited.

    None when the entry is cloud-only (no Modbus connection to reconfigure).
    """
    ctype = entry.data.get(CONF_CONNECTION_TYPE, CONNECTION_TCP)
    if ctype == CONNECTION_CLOUD:
        if not entry.data.get(CONF_MODBUS_ENABLED, False):
            return None
        return entry.data.get(CONF_MODBUS_CONNECTION_TYPE, CONNECTION_TCP)
    return ctype


def _current(entry: ConfigEntry | None, key: str, default: Any) -> Any:
    """Return the effective current value (options override data).

    When ``entry`` is None (e.g. a fresh options flow with no prior entry),
    there is no stored value, so the supplied default is returned.
    """
    if entry is None:
        return default
    return entry.options.get(key, entry.data.get(key, default))


def _build_advanced_schema(
    energy_entity: str,
    offload_enabled: bool,
    offload_url: str,
    offload_db_max_mb: float,
    dir_options: list[str],
    entry: ConfigEntry | None = None,
    modbus_type: str | None = None,
    energy_entity_module_0: str = "",
    energy_entity_module_1: str = "",
    register_map: str = REGISTER_MAP_BATAVIA,
    num_outdoor_units: str = NUM_OUTDOOR_UNITS_SINGLE,
) -> vol.Schema:
    fields: dict[Any, Any] = {}
    _add_register_map(fields, entry, register_map)
    if modbus_type is not None:
        _add_modbus_detail_fields(fields, entry, modbus_type)
    _add_advanced_fields(
        fields,
        energy_entity,
        offload_enabled,
        offload_url,
        offload_db_max_mb,
        dir_options,
        energy_entity_module_0,
        energy_entity_module_1,
        num_outdoor_units=num_outdoor_units,
    )
    return vol.Schema(fields)


def _add_register_map(
    fields: dict[Any, Any], entry: ConfigEntry | None, register_map: str
) -> None:
    """Add the register-map selection field.

    Tells the coordinator which hardware's Modbus address layout to read.
    "batavia" (module 0# system map) for standard units; "newntide" remaps the
    five low-address groups that fail on the Newntide R290 monobloc.
    """
    fields[
        vol.Optional(
            CONF_REGISTER_MAP,
            default=_current(entry, CONF_REGISTER_MAP, register_map),
        )
    ] = SelectSelector(
        SelectSelectorConfig(
            options=[
                SelectOptionDict(
                    value=REGISTER_MAP_BATAVIA,
                    label="BataviaHeat",
                ),
                SelectOptionDict(
                    value=REGISTER_MAP_NEWNTIDE,
                    label="Newntide",
                ),
            ],
            mode=SelectSelectorMode.DROPDOWN,
        )
    )


def _add_modbus_detail_fields(
    fields: dict[Any, Any], entry: ConfigEntry | None, modbus_type: str
) -> None:
    """Add the editable Modbus transport details (host/port or serial/baud)."""
    if modbus_type in (CONNECTION_TCP, CONNECTION_ESP32):
        fields[
            vol.Optional(
                CONF_HOST,
                description={"suggested_value": _current(entry, CONF_HOST, "")},
            )
        ] = str
        fields[
            vol.Optional(
                CONF_TCP_PORT,
                default=_current(entry, CONF_TCP_PORT, DEFAULT_TCP_PORT),
            )
        ] = NumberSelector(
            NumberSelectorConfig(min=1, max=65535, step=1, mode=NumberSelectorMode.BOX)
        )
        fields[
            vol.Optional(
                CONF_SLAVE_ID,
                default=_current(entry, CONF_SLAVE_ID, DEFAULT_SLAVE_ID),
            )
        ] = NumberSelector(
            NumberSelectorConfig(min=0, max=247, step=1, mode=NumberSelectorMode.BOX)
        )
    elif modbus_type == CONNECTION_SERIAL:
        fields[
            vol.Optional(
                CONF_SERIAL_PORT,
                description={"suggested_value": _current(entry, CONF_SERIAL_PORT, "")},
            )
        ] = str
        fields[
            vol.Optional(
                CONF_BAUDRATE,
                default=_current(entry, CONF_BAUDRATE, DEFAULT_BAUDRATE),
            )
        ] = NumberSelector(
            NumberSelectorConfig(min=1200, max=115200, step=1, mode=NumberSelectorMode.BOX)
        )
        fields[
            vol.Optional(
                CONF_SLAVE_ID,
                default=_current(entry, CONF_SLAVE_ID, DEFAULT_SLAVE_ID),
            )
        ] = NumberSelector(
            NumberSelectorConfig(min=0, max=247, step=1, mode=NumberSelectorMode.BOX)
        )


def _add_advanced_fields(
    fields: dict[Any, Any],
    energy_entity: str,
    offload_enabled: bool,
    offload_url: str,
    offload_db_max_mb: float,
    dir_options: list[str],
    energy_entity_module_0: str = "",
    energy_entity_module_1: str = "",
    num_outdoor_units: str = NUM_OUTDOOR_UNITS_SINGLE,
) -> None:
    """Add the device energy meter + register offload fields.

    A single unit (``num_outdoor_units == "1"``) needs one system-wide energy
    meter. A two-unit cascade (``"2"``) additionally exposes a per-unit meter
    for each outdoor unit, so each unit's COP/EER can be computed against its
    own electrical draw.
    """
    if offload_url and offload_url not in dir_options:
        dir_options.append(offload_url)

    # The device's energy meter. For a single unit this is the only meter;
    # for a cascade it measures the whole cascade's total electrical draw
    # (system COP/EER).
    fields[
        vol.Optional(
            CONF_ENERGY_ENTITY,
            description={"suggested_value": energy_entity} if energy_entity else {},
        )
    ] = EntitySelector(EntitySelectorConfig(domain="sensor", device_class="energy"))

    # Per-cascade-unit energy meters. A two-unit cascade has two electrical
    # draws, so assigning a meter per unit lets each unit's COP/EER be computed
    # against its own power (true per-device efficiency).
    if num_outdoor_units == NUM_OUTDOOR_UNITS_CASCADE:
        fields[
            vol.Optional(
                CONF_ENERGY_ENTITY_MODULE_0,
                description={
                    "suggested_value": energy_entity_module_0
                } if energy_entity_module_0 else {},
            )
        ] = EntitySelector(EntitySelectorConfig(domain="sensor", device_class="energy"))
        fields[
            vol.Optional(
                CONF_ENERGY_ENTITY_MODULE_1,
                description={
                    "suggested_value": energy_entity_module_1
                } if energy_entity_module_1 else {},
            )
        ] = EntitySelector(EntitySelectorConfig(domain="sensor", device_class="energy"))

    # Register offload fields (always available).
    fields[vol.Optional(CONF_OFFLOAD_ENABLED, default=offload_enabled)] = bool
    fields[
        vol.Optional(
            CONF_OFFLOAD_URL,
            description={"suggested_value": offload_url} if offload_url else {},
        )
    ] = SelectSelector(
        SelectSelectorConfig(
            options=[SelectOptionDict(value=d, label=d) for d in dir_options],
            mode=SelectSelectorMode.DROPDOWN,
            custom_value=True,
        )
    )
    fields[vol.Optional(CONF_OFFLOAD_DB_MAX_MB, default=offload_db_max_mb)] = NumberSelector(
        NumberSelectorConfig(
            min=0, max=1024000, step=1,
            mode=NumberSelectorMode.BOX,
            unit_of_measurement="MB",
        )
    )


def _build_options_schema(
    entry: ConfigEntry,
    mode: str,
    dir_options: list[str],
    energy_entity: str,
    offload_enabled: bool,
    offload_url: str,
    offload_db_max_mb: float,
    energy_entity_module_0: str,
    energy_entity_module_1: str,
    register_map: str,
    num_outdoor_units: str = NUM_OUTDOOR_UNITS_SINGLE,
) -> vol.Schema:
    """Build the options-flow schema: connection mode + Modbus details + advanced.

    The connection-mode selector (Cloud / Modbus / Both) is the new control;
    Modbus transport + details are shown when the mode is Modbus-only or Both.
    """
    fields: dict[Any, Any] = {}

    # ── Number of outdoor units (single / cascade) ───────────────────────────
    # A single unit needs one system energy meter; a two-unit cascade can assign
    # a meter per unit (or share one for the whole cascade). The connection mode
    # (cloud / Modbus / both) is chosen on the init screen, not here.
    fields[
        vol.Required(
            CONF_NUM_OUTDOOR_UNITS,
            default=num_outdoor_units,
        )
    ] = SelectSelector(
        SelectSelectorConfig(
            options=[
                SelectOptionDict(
                    value=NUM_OUTDOOR_UNITS_SINGLE, label="1 outdoor unit"
                ),
                SelectOptionDict(
                    value=NUM_OUTDOOR_UNITS_CASCADE, label="2 outdoor units (cascade)"
                ),
            ]
        )
    )

    # ── Editable Modbus transport + details (IP/baud can change over time) ─────
    if mode in (CONNECTION_MODE_MODBUS, CONNECTION_MODE_BOTH):
        modbus_type = _effective_modbus_type(entry) or CONNECTION_TCP
        fields[
            vol.Required(CONF_MODBUS_CONNECTION_TYPE, default=modbus_type)
        ] = SelectSelector(
            SelectSelectorConfig(
                options=[
                    SelectOptionDict(
                        value=CONNECTION_TCP, label="DR164 gateway (Modbus TCP)"
                    ),
                    SelectOptionDict(
                        value=CONNECTION_ESP32, label="ESP32 proxy (Modbus TCP)"
                    ),
                    SelectOptionDict(
                        value=CONNECTION_SERIAL, label="Modbus RTU (Serial)"
                    ),
                ]
            )
        )
        _add_modbus_detail_fields(fields, entry, modbus_type)

    # ── Register map + energy meter + offload ─────────────────────────────────
    _add_register_map(fields, entry, register_map)
    _add_advanced_fields(
        fields,
        energy_entity,
        offload_enabled,
        offload_url,
        offload_db_max_mb,
        dir_options,
        energy_entity_module_0,
        energy_entity_module_1,
        num_outdoor_units=num_outdoor_units,
    )
    return vol.Schema(fields)


def _normalize_advanced_options(
    user_input: dict[str, Any],
    modbus_type: str | None = None,
    num_outdoor_units: str = NUM_OUTDOOR_UNITS_SINGLE,
) -> dict[str, Any]:
    options = dict(user_input)
    # Connection-mode inputs live in entry.data, not options — drop them so
    # entry.options holds only the genuinely-advanced settings.
    for key in _CONNECTION_INPUT_KEYS:
        options.pop(key, None)
    options.setdefault(CONF_NUM_OUTDOOR_UNITS, num_outdoor_units)
    options.setdefault(CONF_ENERGY_ENTITY, "")
    options.setdefault(CONF_ENERGY_ENTITY_MODULE_0, "")
    options.setdefault(CONF_REGISTER_MAP, REGISTER_MAP_BATAVIA)
    options.setdefault(CONF_ENERGY_ENTITY_MODULE_1, "")
    options.setdefault(CONF_OFFLOAD_URL, "")
    options.setdefault(CONF_OFFLOAD_ENABLED, False)
    options.setdefault(CONF_OFFLOAD_DB_MAX_MB, DEFAULT_OFFLOAD_DB_MAX_MB)

    # Cascade with a single meter: that meter measures the whole cascade, so
    # it must be assigned to both module keys. A blank per-unit pair falls back
    # to the system energy_entity when one is provided.
    if num_outdoor_units == NUM_OUTDOOR_UNITS_CASCADE:
        m0 = options[CONF_ENERGY_ENTITY_MODULE_0]
        m1 = options[CONF_ENERGY_ENTITY_MODULE_1]
        if m0 and not m1:
            options[CONF_ENERGY_ENTITY_MODULE_1] = m0
        elif m1 and not m0:
            options[CONF_ENERGY_ENTITY_MODULE_0] = m1
        elif not m0 and not m1 and options[CONF_ENERGY_ENTITY]:
            options[CONF_ENERGY_ENTITY_MODULE_0] = options[CONF_ENERGY_ENTITY]
            options[CONF_ENERGY_ENTITY_MODULE_1] = options[CONF_ENERGY_ENTITY]
    return options


# Form keys that describe the connection itself (stored in entry.data, not
# entry.options). Kept in one place so _normalize_advanced_options strips them.
_CONNECTION_INPUT_KEYS = (
    CONF_CONNECTION_TYPE,
    CONF_MODBUS_CONNECTION_TYPE,
    CONF_HOST,
    CONF_TCP_PORT,
    CONF_SLAVE_ID,
    CONF_SERIAL_PORT,
    CONF_BAUDRATE,
)


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