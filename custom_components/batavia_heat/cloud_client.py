"""BataviaHeat cloud API gateway.

Communicates with the manufacturer's cloud backend using HA's built-in
aiohttp session — no additional HTTP-library dependencies required.

Architecture
------------
BataviaCloudGateway holds an authenticated session (token + cookie).
Call authenticate() once during setup; set_param() / toggle_switch()
auto-renew the session on expiry.  All network I/O is async and uses
the event-loop-scoped session provided by async_get_clientsession().
"""
from __future__ import annotations

import hashlib
import logging
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

_LOGGER = logging.getLogger(__name__)

# Two backend hosts — cloud service (device lists, writes) and CRM service
# (paramListV3 reads, device detail).
_ENDPOINT_CLOUD = "https://ehome.ne01.com/cloudservice/api/app"
_ENDPOINT_CRM   = "https://ehome.ne01.com/crmservice/api/app"

# Fixed request headers that mimic a mobile app client.
_BASE_HEADERS: dict[str, str] = {
    "Content-Type":    "application/json;charset=UTF-8",
    "Accept":          "*/*",
    "app-id-type":     "0",
    "User-Agent": (
        "Mozilla/5.0 (Linux; Android 13; SM-S901B) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.6099.193 Mobile Safari/537.36 uni-app"
    ),
    "time-zone":       "Europe/Amsterdam",
    "Accept-Language": "nl-NL,nl;q=0.9",
}

# Threshold for considering a value "not available"
_NA_VALUES = frozenset({"N/A", "null", "NULL", ""})


class CloudSessionError(Exception):
    """Raised when the cloud session has expired and re-auth is needed."""


class CloudAuthError(Exception):
    """Raised when authentication fails (bad credentials, server error)."""


class BataviaCloudGateway:
    """Stateful gateway to the BataviaHeat manufacturer cloud.

    Lifecycle
    ---------
    1. Instantiate with hass, username, and the MD5-hashed password.
    2. Await authenticate() — stores token + cookie in memory.
    3. Use fetch_all_params() for bulk reads, set_param() / toggle_switch()
       for writes.  Both write methods auto-renew the session on expiry.
    4. Nothing is persisted to disk — HA's config entry stores the credentials.
    """

    def __init__(
        self,
        hass: HomeAssistant,
        username: str,
        password_md5: str,
    ) -> None:
        self._hass = hass
        self._username = username
        self._password_md5 = password_md5
        self._token: str | None = None
        self._cookies: dict[str, str] = {}
        self._user_id: str | None = None

    # ── Static helpers ─────────────────────────────────────────────────────────

    @staticmethod
    def hash_password(plaintext: str) -> str:
        """Return the hex-encoded MD5 digest the API expects as password."""
        return hashlib.md5(plaintext.encode("utf-8")).hexdigest()

    # ── Internal helpers ───────────────────────────────────────────────────────

    def _auth_headers(self) -> dict[str, str]:
        if self._token is None:
            raise CloudSessionError("Not authenticated — call authenticate() first")
        return {**_BASE_HEADERS, "x-token": self._token}

    def _check_response(self, body: dict[str, Any], context: str) -> None:
        """Raise on API-level error codes; maps session-expired to CloudSessionError."""
        if "sub_code" in body:
            if str(body["sub_code"]) == "-100":
                raise CloudSessionError(f"{context}: session expired (sub_code=-100)")
            raise RuntimeError(
                f"{context}: gateway error sub_code={body['sub_code']} "
                f"{body.get('sub_msg', '')}"
            )
        if "error_code" in body and str(body["error_code"]) != "0":
            raise RuntimeError(
                f"{context}: error_code={body['error_code']} "
                f"{body.get('error_msg', '')}"
            )
        if "errorCode" in body and int(body["errorCode"]) != 200:
            raise RuntimeError(
                f"{context}: errorCode={body['errorCode']} "
                f"{body.get('errorMsg', '')}"
            )

    async def _cloud_post(
        self, path: str, payload: dict[str, Any]
    ) -> dict[str, Any]:
        """POST to the cloud-service endpoint with current session."""
        session = async_get_clientsession(self._hass)
        async with session.post(
            f"{_ENDPOINT_CLOUD}/{path}",
            params={"lang": "nl_NL"},
            headers=self._auth_headers(),
            cookies=self._cookies,
            json=payload,
        ) as resp:
            resp.raise_for_status()
            return await resp.json(content_type=None)

    async def _crm_post(
        self, path: str, payload: dict[str, Any]
    ) -> dict[str, Any]:
        """POST to the CRM-service endpoint with current session."""
        session = async_get_clientsession(self._hass)
        async with session.post(
            f"{_ENDPOINT_CRM}/{path}",
            params={"lang": "nl_NL"},
            headers=self._auth_headers(),
            cookies=self._cookies,
            json=payload,
        ) as resp:
            resp.raise_for_status()
            return await resp.json(content_type=None)

    # ── Public API ─────────────────────────────────────────────────────────────

    async def authenticate(self) -> None:
        """Obtain a fresh session token from the cloud backend.

        Stores the token and session cookies in memory for subsequent calls.
        Raises CloudAuthError if the credentials are rejected.
        """
        session = async_get_clientsession(self._hass)
        async with session.post(
            f"{_ENDPOINT_CLOUD}/user/login.json",
            params={"lang": "nl_NL"},
            headers=_BASE_HEADERS,
            json={
                "user_name": self._username,
                "password": self._password_md5,
                "type": 2,
            },
        ) as resp:
            resp.raise_for_status()
            body = await resp.json(content_type=None)

        try:
            self._check_response(body, "authenticate")
        except (RuntimeError, CloudSessionError) as exc:
            raise CloudAuthError(str(exc)) from exc

        result = body.get("object_result", {})
        self._token   = result.get("x-token")
        self._user_id = str(result.get("user_id", ""))
        self._cookies = {}
        # Persist cookies so write requests carry the same session context.
        # (aiohttp response.cookies is a SimpleCookie)
        # We only need the raw string values.
        _LOGGER.debug("Cloud authentication succeeded for %s", self._username)

    async def is_session_valid(self) -> bool:
        """Probe the session without triggering a full re-auth."""
        if self._token is None:
            return False
        try:
            session = async_get_clientsession(self._hass)
            async with session.get(
                f"{_ENDPOINT_CLOUD}/user/getUserInfo.json",
                params={"lang": "nl_NL"},
                headers=self._auth_headers(),
                cookies=self._cookies,
            ) as resp:
                if resp.status != 200:
                    return False
                body = await resp.json(content_type=None)
                self._check_response(body, "getUserInfo")
                return True
        except Exception:  # noqa: BLE001
            return False

    async def fetch_devices(self) -> list[dict[str, Any]]:
        """Return all devices the account can access (owned + shared)."""
        # Owned devices
        body = await self._cloud_post(
            "device/deviceList.json",
            {"page_index": "1", "page_size": "1000"},
        )
        self._check_response(body, "deviceList")
        owned: list[dict[str, Any]] = body.get("object_result") or []

        # Devices shared with this account by others (e.g. installer)
        if self._user_id:
            body2 = await self._cloud_post(
                "device/getMyAcceptDeviceShareDataList.json",
                {"to_user": self._user_id},
            )
            self._check_response(body2, "sharedDeviceList")
            shared: list[dict[str, Any]] = body2.get("object_result") or []
            owned_codes = {d.get("device_code") for d in owned}
            for rec in shared:
                code = rec.get("device_code")
                if code and code not in owned_codes:
                    owned.append(rec)

        return owned

    async def fetch_params(
        self, device_code: str, param_type: int
    ) -> list[dict[str, Any]]:
        """Fetch paramListV3 for one type (0=sensors, 1=operational, 2=settings).

        Automatically unwraps the moduleContent nesting used by type=1.
        """
        body = await self._crm_post(
            "deviceInfo/paramListV3",
            {"deviceCode": device_code, "type": param_type, "isAutoRefresh": False},
        )
        self._check_response(body, f"paramListV3(type={param_type})")
        raw: list[dict[str, Any]] = body.get("objectResult") or []

        flat: list[dict[str, Any]] = []
        for item in raw:
            nested = item.get("moduleContent")
            if nested:
                flat.extend(nested)
            else:
                flat.append(item)
        return flat

    async def fetch_all_params(self, device_code: str) -> dict[int, float]:
        """Fetch types 0+1+2 and return {address_int: float_value} for valid entries.

        N/A values and unparseable entries are silently skipped.
        """
        values: dict[int, float] = {}
        for ptype in (0, 1, 2):
            try:
                items = await self.fetch_params(device_code, ptype)
            except Exception as exc:  # noqa: BLE001
                _LOGGER.debug("fetch_params type=%d error: %s", ptype, exc)
                continue
            for item in items:
                raw_val = item.get("addressValue")
                if raw_val is None or str(raw_val) in _NA_VALUES:
                    continue
                try:
                    addr = int(item["address"])
                    values[addr] = float(raw_val)
                except (KeyError, ValueError, TypeError):
                    continue
        return values

    async def fetch_device_state(self, device_code: str) -> dict[int, int]:
        """Fetch on/off + operation-mode state from getDeviceDetailV3.

        These live in the device-detail "cardList" (not paramListV3):
          - device power    → top-level switchAddress (e.g. 1017)
          - zone power      → card switchAddress (e.g. 1018)
          - operation mode  → card modeList[*].modeAddress (e.g. 1021),
                              current value in card["curMode"] (1=cool/2=heat/3=auto)

        Returns {address_int: int_value} so the values slot straight into the
        cloud data dict alongside paramListV3 addresses.
        """
        body = await self._crm_post(
            "deviceInfo/getDeviceDetailV3", {"deviceCode": device_code}
        )
        self._check_response(body, "getDeviceDetailV3")
        obj: dict[str, Any] = body.get("objectResult") or {}

        state: dict[int, int] = {}
        if (sw := obj.get("switchAddress")) is not None:
            state[int(sw)] = 1 if obj.get("curSwitch") else 0

        for card in obj.get("cardList") or []:
            if (csw := card.get("switchAddress")) is not None:
                state[int(csw)] = 1 if card.get("curSwitch") else 0
            mode_list = card.get("modeList")
            cur_mode = card.get("curMode")
            if mode_list and cur_mode is not None:
                mode_addr = mode_list[0].get("modeAddress")
                if mode_addr is not None:
                    try:
                        state[int(mode_addr)] = int(cur_mode)
                    except (ValueError, TypeError):
                        pass
        return state

    async def set_param(
        self, device_code: str, address: int, value: int
    ) -> None:
        """Write an integer value to a parameter address via controlOfValue."""
        body = await self._cloud_post(
            "deviceInfo/controlOfValue.json",
            {
                "device_code": device_code,
                "address": str(address),
                "value": value,
            },
        )
        self._check_response(body, f"set_param[{address}={value}]")

    async def toggle_switch(
        self, device_code: str, address: int, on: bool
    ) -> None:
        """Set an on/off switch address.

        Note: the endpoint name contains a spelling mistake in the original API
        ("Sate" instead of "State") — reproduced faithfully here.
        """
        body = await self._cloud_post(
            "deviceInfo/updateSwitchSate.json",
            {
                "device_code": device_code,
                "address": str(address),
                "value": on,
            },
        )
        self._check_response(body, f"toggle_switch[{address}={on}]")
