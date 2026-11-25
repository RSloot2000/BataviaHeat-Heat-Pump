#!/usr/bin/env python3
"""General scanner for the New Energy Eco-Home heat-pump cloud backend.

This tool logs into the manufacturer's Eco-Home cloud and dumps everything it
can read for a device:

* every parameter from ``paramListV3`` (types 0 = sensors, 1 = operational,
  2 = settings), sorted by address, with name / value / unit / type;
* the full ``getDeviceDetailV3`` card layout (switch addresses, modes, current
  and target temperatures) so you can see exactly what the cloud publishes.

It is intentionally generic -- no assumptions about specific registers -- so it
is useful as an exploratory tool: run it, study the output, and pick out the
addresses you care about (for example to wire them into a local Modbus mapping).

It is fully self-contained (Python standard library only, no third-party
dependencies) so any user can run it next to their Python installation.

Usage
-----
    python scan_ecohome.py --username you@example.com --password "secret"
    python scan_ecohome.py --username you@example.com            # ECOHOME_PASSWORD
    python scan_ecohome.py --credentials ~/.ecohome/credentials.json
    python scan_ecohome.py --device WQ1A25032561 --json

Environment variables: ECOHOME_USER, ECOHOME_PASSWORD, ECOHOME_CREDENTIALS.
"""
from __future__ import annotations

import argparse
import hashlib
import http.cookiejar
import json
import os
import sys
import urllib.error
import urllib.request

CLOUD = "https://ehome.ne01.com/cloudservice/api/app"
CRM = "https://ehome.ne01.com/crmservice/api/app"

HEADERS = {
    "Content-Type": "application/json;charset=UTF-8",
    "Accept": "*/*",
    "app-id-type": "0",
    "User-Agent": (
        "Mozilla/5.0 (Linux; Android 13; SM-S901B) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0.6099.193 Mobile Safari/537.36 uni-app"
    ),
    "time-zone": "Europe/Amsterdam",
    "Accept-Language": "nl-NL,nl;q=0.9",
}

_TIMEOUT = 30


class CloudError(RuntimeError):
    """Generic cloud API error."""


class SessionExpiredError(CloudError):
    """Session has expired and must be renewed."""


def _check_response(body: dict, context: str) -> None:
    """Map the API error envelopes onto CloudError / SessionExpiredError."""
    if "sub_code" in body:
        if str(body["sub_code"]) == "-100":
            raise SessionExpiredError(f"{context}: session expired (sub_code=-100)")
        raise CloudError(f"{context}: sub_code={body['sub_code']} {body.get('sub_msg', '')}")
    if "error_code" in body and str(body["error_code"]) != "0":
        raise CloudError(f"{context}: error_code={body['error_code']} {body.get('error_msg', '')}")
    if "errorCode" in body and int(body["errorCode"]) != 200:
        raise CloudError(f"{context}: errorCode={body['errorCode']} {body.get('errorMsg', '')}")


class EcoHomeClient:
    """Minimal, dependency-free client for the Eco-Home cloud API."""

    def __init__(self) -> None:
        self.token: str | None = None
        self.user_id: str | None = None
        self.username: str | None = None
        self._password_md5: str | None = None
        self._cookie_header: str = ""
        self._cookies = http.cookiejar.CookieJar()
        self._opener = urllib.request.build_opener(
            urllib.request.HTTPCookieProcessor(self._cookies)
        )

    # ── transport ────────────────────────────────────────────────────────────

    def _request(self, url: str, payload: dict | None = None, method: str = "POST") -> dict:
        data = json.dumps(payload).encode() if payload is not None else None
        req = urllib.request.Request(url, data=data, method=method)
        for key, value in HEADERS.items():
            req.add_header(key, value)
        if self._cookie_header:
            req.add_header("Cookie", self._cookie_header)
        if self.token:
            req.add_header("x-token", self.token)
        try:
            with self._opener.open(req, timeout=_TIMEOUT) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:  # pragma: no cover - network edge
            raw = exc.read().decode("utf-8", "replace")[:300]
            raise CloudError(f"{method} {url} -> HTTP {exc.code}: {raw}") from exc

    # ── auth ─────────────────────────────────────────────────────────────────

    def login(self, username: str, password: str, force: bool = False) -> None:
        """Fresh login with a plaintext password (hashed to MD5 for the API)."""
        self.username = username
        self._password_md5 = hashlib.md5(password.encode()).hexdigest()
        self._do_login(force=force)

    def load_session(self, creds: dict, username: str) -> None:
        """Reuse a previously saved session (token + cookie), no password needed."""
        self.username = username
        record = creds.get(username) or next(iter(creds.values()))
        self.token = record.get("x_token")
        self.user_id = record.get("user_id")
        self._cookie_header = "; ".join(
            f"{name}={value}" for name, value in (record.get("cookie") or {}).items()
        )

    def _do_login(self, force: bool = False) -> None:
        if not force and self._session_valid():
            return
        body = self._request(
            f"{CLOUD}/user/login.json",
            {"user_name": self.username, "password": self._password_md5, "type": 2},
        )
        _check_response(body, "login")
        result = body.get("object_result") or {}
        self.token = result.get("x-token")
        self.user_id = str(result.get("user_id", ""))

    def _session_valid(self) -> bool:
        try:
            body = self._request(f"{CLOUD}/user/getUserInfo.json")
            _check_response(body, "getUserInfo")
            return True
        except (CloudError, urllib.error.URLError, TimeoutError, OSError):
            return False

    def _crm_request(self, endpoint: str, body_in: dict, retries: int = 1) -> dict:
        """POST to crmservice, renewing the session once on expiry."""
        url = f"{CRM}/{endpoint}"
        for _ in range(retries + 1):
            try:
                return self._request(url, body_in)
            except SessionExpiredError:
                if _ == retries or not self._password_md5:
                    raise
                self._do_login(force=True)
        raise CloudError(f"{endpoint}: exhausted retries")  # pragma: no cover

    # ── data ─────────────────────────────────────────────────────────────────

    def list_devices(self) -> list[dict]:
        body = self._request(
            f"{CLOUD}/device/deviceList.json",
            {"page_index": "1", "page_size": "1000"},
        )
        _check_response(body, "deviceList")
        return body.get("object_result") or []

    def list_shared_devices(self) -> list[dict]:
        if not self.user_id:
            return []
        body = self._request(
            f"{CLOUD}/device/getMyAcceptDeviceShareDataList.json",
            {"to_user": self.user_id},
        )
        _check_response(body, "sharedDeviceList")
        return body.get("object_result") or []

    def get_device_detail(self, device_code: str) -> dict:
        body = self._crm_request("deviceInfo/getDeviceDetailV3", {"deviceCode": device_code})
        _check_response(body, "getDeviceDetailV3")
        return body.get("objectResult") or {}

    def get_param_list(self, device_code: str, param_type: int) -> list[dict]:
        body = self._crm_request(
            "deviceInfo/paramListV3",
            {"deviceCode": device_code, "type": param_type, "isAutoRefresh": False},
        )
        _check_response(body, f"paramListV3(type={param_type})")
        raw = body.get("objectResult") or []
        flat: list[dict] = []
        for item in raw:
            if "moduleContent" in item:
                flat.extend(item["moduleContent"])
            else:
                flat.append(item)
        return flat


# ── scanning helpers ──────────────────────────────────────────────────────────

def _flatten(param_type: int, raw: list[dict]) -> list[dict]:
    flat: list[dict] = []
    for item in raw:
        if "moduleContent" in item:
            flat.extend(item["moduleContent"])
        else:
            flat.append(item)
    return flat


def _collect_params(client: EcoHomeClient, device_code: str) -> dict[int, dict]:
    """Return {address: {name, point_name, value, unit, type, available}} for
    every parameter the backend reports.

    Types 0 (sensors) and 1 (operational) are the live readings; type 2 holds
    the adjustable settings. Every parameter the backend lists is included --
    even unavailable ones (value N/A / null) -- so nothing is hidden. An entry
    is only skipped when it has no usable address to key on.

    The human-readable label comes from the backend's ``addressNum`` slug
    (e.g. ``indoor_temp``), which the cloud returns with every response and
    updates over time -- so no static translation map is needed and the names
    stay in sync with the backend. When the backend does not provide
    ``addressNum`` we fall back to the raw ``pointName``.
    """
    params: dict[int, dict] = {}
    for ptype in (0, 1, 2):
        for item in _flatten(ptype, client.get_param_list(device_code, ptype)):
            raw_addr = item.get("address")
            if raw_addr is None:
                continue
            try:
                addr = int(str(raw_addr).strip())
            except (ValueError, TypeError):
                continue
            raw_val = item.get("addressValue")
            point_name = item.get("pointName")
            slug = item.get("addressNum")
            name = (slug or point_name or str(raw_addr)).strip()
            params[addr] = {
                "name": name,
                "point_name": point_name,
                "value": raw_val,
                "unit": item.get("unit") or "",
                "type": ptype,
                "available": not _is_na_value(raw_val),
            }
    return params


def _is_na_value(value) -> bool:
    """True when a raw param value should be treated as unavailable."""
    if value is None:
        return True
    return str(value).strip().lower() in {"", "null", "n/a"}


def _fmt_value(value) -> str:
    """Render a raw param value for display, normalising missing values."""
    if value is None:
        return "N/A"
    if isinstance(value, float):
        return f"{value:g}"
    text = str(value).strip()
    return text if text and text.lower() not in ("null", "n/a") else "N/A"


def _select_device(client: EcoHomeClient, device: str | None) -> str:
    if device:
        return device
    devices = client.list_devices() + client.list_shared_devices()
    if not devices:
        print("Error: no devices found for this account.", file=sys.stderr)
        sys.exit(1)
    if len(devices) == 1:
        return devices[0]["device_code"]
    print("Multiple devices found. Choose one with --device:\n")
    for d in devices:
        print(f"  {d.get('device_code'):16} {d.get('device_nick_name', '')}")
    sys.exit(1)


def _load_credentials(path: str) -> dict:
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="scan_ecohome",
        description="Dump everything the Eco-Home cloud exposes for a heat pump.",
    )
    parser.add_argument("--username", help="Login username (or ECOHOME_USER).")
    parser.add_argument("--password", help="Login password (or ECOHOME_PASSWORD).")
    parser.add_argument(
        "--credentials", help="Path to a saved ecohome credentials JSON to reuse."
    )
    parser.add_argument("--device", help="Device code (auto-selected if only one exists).")
    parser.add_argument("--force", action="store_true", help="Force a fresh login.")
    parser.add_argument("--json", action="store_true", help="Machine-readable output.")
    return parser.parse_args()


def _build_client(args: argparse.Namespace) -> EcoHomeClient:
    client = EcoHomeClient()
    username = args.username or os.environ.get("ECOHOME_USER")
    password = args.password or os.environ.get("ECOHOME_PASSWORD")
    cred_path = args.credentials or (
        os.environ.get("ECOHOME_CREDENTIALS")
        if os.path.exists(os.environ.get("ECOHOME_CREDENTIALS", ""))
        else None
    )

    if cred_path:
        client.load_session(_load_credentials(cred_path), username or next(iter(_load_credentials(cred_path))))
        return client
    if username and password:
        client.login(username, password, force=bool(args.force))
        return client
    if not username:
        print("Error: no username. Pass --username or set ECOHOME_USER.", file=sys.stderr)
        sys.exit(1)
    print("Error: no password. Pass --password / ECOHOME_PASSWORD or --credentials.",
          file=sys.stderr)
    sys.exit(1)


# ── reporting ─────────────────────────────────────────────────────────────────

def _print_params(device_code: str, params: dict[int, dict]) -> None:
    print(f"Eco-Home cloud scan for device: {device_code}\n")
    print(f"{'ADDR':>6}  {'TYPE':<4}  {'VALUE':<12}  NAME")
    print("-" * 70)
    for addr in sorted(params):
        info = params[addr]
        avail = "" if info.get("available") else "  (unavailable)"
        print(f"{addr:>6}  {info['type']:<4}  {_fmt_value(info['value'])}{info['unit']:<6}  {info['name']}{avail}")
    unavailable = sum(1 for i in params.values() if not i.get("available"))
    print(f"\nTotal params: {len(params)} "
          f"({unavailable} unavailable) "
          "(type 0 = sensors, 1 = operational, 2 = settings).")


# Minimal, stable-keyed English localisation for device operating modes.
# The backend always returns modeMeaning in Chinese regardless of the requested
# language and provides no English slug for modes, so we key on the numeric
# modeValue (the register code, far more stable than the Chinese text) and fall
# back to the raw meaning for anything not in the map.
_MODE_MEANINGS: dict[int, str] = {1: "Cooling", 2: "Heating", 3: "Auto"}


def _mode_label(mode: dict) -> str:
    """Localise a single mode entry to English, falling back to the raw text."""
    value = mode.get("modeValue")
    chinese = mode.get("modeMeaning")
    try:
        key = int(value)
    except (ValueError, TypeError):
        key = None
    english = _MODE_MEANINGS.get(key) if key is not None else None
    if english:
        return f"{english} (mode {key})"
    return f"{chinese} (mode {value})"


def _print_cards(detail: dict) -> None:
    print("\n=== Device detail (getDeviceDetailV3) ===")
    print(f"master switchAddress={detail.get('switchAddress')} "
          f"curSwitch={bool(detail.get('curSwitch'))}")
    cards = detail.get("cardList") or []
    if not cards:
        print("  (no cards)")
    for card in cards:
        print(f"\nCard {card.get('card')!r} name={card.get('cardName')}")
        print(f"  switchAddress={card.get('switchAddress')} "
              f"curSwitch={bool(card.get('curSwitch'))}")
        print(f"  settingAddress={card.get('settingAddress')} "
              f"settingTemp={card.get('settingTemp')} "
              f"curTempMain={card.get('curTempMain')}")
        modes = card.get("modeList") or []
        if modes:
            mode_addr = modes[0].get("modeAddress")
            parts = [_mode_label(m) for m in modes]
            print(f"  modeAddress={mode_addr} modes={', '.join(parts)}")


def _report_json(device_code: str, params: dict[int, dict], detail: dict) -> None:
    out = {
        "device_code": device_code,
        "detail": detail,
        "params": {
            str(a): {
                "name": i["name"],
                "point_name": i.get("point_name"),
                "value": i["value"],
                "unit": i["unit"],
                "type": i["type"],
                "available": i.get("available"),
            }
            for a, i in sorted(params.items())
        },
        "total_params": len(params),
    }
    print(json.dumps(out, indent=2, ensure_ascii=False))


def main() -> int:
    args = _parse_args()
    # The cloud returns Chinese point names and the ℃ symbol; force UTF-8 so
    # the dump renders correctly on consoles that default to a codepage like
    # cp1252.
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except (AttributeError, OSError):  # pragma: no cover - platform edge
        pass
    try:
        client = _build_client(args)
        device_code = _select_device(client, args.device)
        params = _collect_params(client, device_code)
        detail = client.get_device_detail(device_code)
    except SessionExpiredError:
        print(
            "Error: the cloud param API needs a fresh login. Provide "
            "--username/--password (or a credentials file with a password) "
            "so the session can be renewed.",
            file=sys.stderr,
        )
        return 2
    except (CloudError, urllib.error.URLError, OSError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2

    if args.json:
        _report_json(device_code, params, detail)
    else:
        _print_params(device_code, params)
        _print_cards(detail)
    return 0


if __name__ == "__main__":
    sys.exit(main())
