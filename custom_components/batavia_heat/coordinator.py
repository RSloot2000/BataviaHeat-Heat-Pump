"""DataUpdateCoordinator for BataviaHeat R290.

TCP connections use raw-socket tablet-synchronized bus-sharing:
the DR164 RS485-to-WiFi gateway shares the bus with the manufacturer's tablet,
which polls the heat pump every ~1.3s using FC03. This coordinator detects the
tablet's polling cycle end and reads in the ~400ms free window. Count validation
and automatic retries ensure zero corrupt data reaches Home Assistant.

Serial connections use standard pymodbus (no bus sharing needed).
"""
from __future__ import annotations

import asyncio
import logging
import struct
from datetime import timedelta
from typing import Any

from pymodbus.client import ModbusSerialClient, ModbusTcpClient
from pymodbus.exceptions import ConnectionException, ModbusException

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .cloud_client import BataviaCloudGateway, CloudAuthError, CloudSessionError
from .const import (
    CLOUD_FAILURE_THRESHOLD,
    CONF_BAUDRATE,
    CONF_CLOUD_DEVICE_CODE,
    CONF_CLOUD_PASSWORD_HASH,
    CONF_CLOUD_USERNAME,
    CONF_CONNECTION_TYPE,
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
    DEFAULT_CLOUD_SCAN_INTERVAL,
    DEFAULT_OFFLOAD_DB_MAX_MB,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    HOLDING_REGISTERS,
    INPUT_REGISTERS,
    SENSOR_DISCONNECTED,
)

_LOGGER = logging.getLogger(__name__)

# ── Read group definitions ──
# Split by function code — FC03≠FC04 for addresses 135+.

# FC03 — Holding registers (operational, config, setpoints)
# NOTE: HR[768-776] must be read individually. Batch read (768, 9) returns only
# 8 registers (count mismatch → rejected) AND reports HR[772] as 0 instead of
# the actual heating setpoint. Individual reads return correct values.
_HOLDING_READ_GROUPS: list[tuple[int, int]] = [
    (768, 1),     # HR[768]: operational status
    (772, 1),     # HR[772]: heating target setpoint (MUST be individual read)
    (773, 1),     # HR[773]: compressor discharge temperature
    (776, 1),     # HR[776]: water outlet temperature
    (912, 2),     # HR[912-913]: unit power + silent-mode state mirrors
    (1283, 1),    # HR[1283]: compressor running
    (1348, 3),    # HR[1348-1350]: plate HX water temps + total water outlet
    (3230, 2),    # HR[3230-3231]: buffer inlet/outlet temperatures
    (6400, 1),    # HR[6400]: working mode (1=cool, 2=heat, 3=auto)
    (6401, 8),    # HR[6401-6408]: cool/heat setpoints + room targets + zone B
    (6425, 12),   # HR[6425-6436]: zone A/B curves + cool/heat custom curve pts
    (6465, 1),    # HR[6465]: N01 power mode
    (6472, 1),    # HR[6472]: P01 pump operating mode
    (6507, 1),    # HR[6507]: P09 pump intermittent stop time
    (6511, 1),    # HR[6511]: P20 pump intermittent run time
    (7184, 7),    # HR[7184-7190]: M35-M40 auto-cool/holiday/aux/ext heat source
    (7232, 8),    # HR[7232-7239]: P02-P08 pump control/speed/flow/interval
]

# FC04 — Input registers (live sensor data from heat pump hardware)
_INPUT_READ_GROUPS: list[tuple[int, int]] = [
    (22, 4),      # IR[22-25]: ambient, fin coil, suction, discharge temps
    (32, 2),      # IR[32-33]: low/high pressure
    (53, 2),      # IR[53-54]: pump target speed, flow rate
    (66, 1),      # IR[66]: pump control signal
    (135, 8),     # IR[135-142]: HX temps, module temps, pump feedback
]

# Combined read list for TCP: FC04 first (tablet only uses FC03 → zero
# collision risk), then FC03 (may collide, retries handle it).
_TCP_READ_GROUPS: list[tuple[int, int, int]] = [
    *[(4, start, count) for start, count in _INPUT_READ_GROUPS],
    *[(3, start, count) for start, count in _HOLDING_READ_GROUPS],
]

# Tablet bus-sharing constants
_MAX_READ_RETRIES = 3
_TABLET_CYCLE_END_REGS = 54   # Tablet's last FC03 response has 54 registers
_SINGLE_READ_TIMEOUT = 2.0    # Max wait for one Modbus response (seconds)
_CYCLE_DETECT_TIMEOUT = 5.0   # Max wait for tablet cycle-end marker (seconds)
_NO_TABLET_TIMEOUT = 1.0      # Shorter cycle-detect timeout when tablet known absent
_NO_TABLET_THRESHOLD = 3      # Consecutive misses before switching to direct mode

# Build lookup: address → (dict_key, reg_info) for fast dispatch after bulk read
_ADDR_MAP: dict[int, tuple[str, dict]] = {}
for _addr, _info in HOLDING_REGISTERS.items():
    _ADDR_MAP[_addr] = ("holding", _info)
for _addr, _info in INPUT_REGISTERS.items():
    _ADDR_MAP[_addr] = ("input", _info)

# ── Snapshot consolidation ──
# How often to merge offloaded snap_*.json files into snapshots.db.
CONSOLIDATE_INTERVAL = timedelta(minutes=30)
# Database filename created inside the offload directory.
CONSOLIDATE_DB_NAME = "snapshots.db"
# Long-format schema: one snapshot row + one row per register reading.
_CONSOLIDATE_SCHEMA = """
CREATE TABLE IF NOT EXISTS snapshots (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    ts        TEXT NOT NULL,
    host      TEXT,
    slave_id  INTEGER
);
CREATE TABLE IF NOT EXISTS readings (
    snapshot_id INTEGER NOT NULL,
    reg_type    TEXT NOT NULL,
    address     INTEGER NOT NULL,
    value       INTEGER,
    FOREIGN KEY (snapshot_id) REFERENCES snapshots(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_snapshots_ts ON snapshots(ts);
CREATE INDEX IF NOT EXISTS idx_readings_addr ON readings(reg_type, address);
"""


class BataviaHeatCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Coordinator to manage fetching data from BataviaHeat R290.

    Supports three operating modes:
    - Modbus-only (tcp / esp32 / serial): existing behaviour, unchanged.
    - Cloud-only: polls the EcoHome cloud API every 30 s.
    - Cloud + Modbus: cloud is primary (30 s), Modbus runs as backup/extension.
      When the cloud is unreachable for CLOUD_FAILURE_THRESHOLD consecutive
      cycles the coordinator falls back to Modbus-only until the cloud recovers.
    """

    config_entry: ConfigEntry

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialize the coordinator."""
        self._connection_type = entry.data.get(CONF_CONNECTION_TYPE, CONNECTION_TCP)
        scan_secs = (
            DEFAULT_CLOUD_SCAN_INTERVAL
            if self._connection_type == CONNECTION_CLOUD
            else DEFAULT_SCAN_INTERVAL
        )
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=scan_secs),
        )
        self.config_entry = entry
        self._slave_id = entry.options.get(
            CONF_SLAVE_ID, entry.data.get(CONF_SLAVE_ID, 1)
        )

        # ── Cloud state ────────────────────────────────────────────────────────
        self._cloud: BataviaCloudGateway | None = None
        self._cloud_device_code: str = ""
        self._cloud_active: bool = False
        self._cloud_failures: int = 0
        self._modbus_enabled: bool = False
        self._modbus_connection_type: str = CONNECTION_TCP

        if self._connection_type == CONNECTION_CLOUD:
            self._cloud = BataviaCloudGateway(
                hass,
                entry.data[CONF_CLOUD_USERNAME],
                entry.data[CONF_CLOUD_PASSWORD_HASH],
            )
            self._cloud_device_code = entry.data[CONF_CLOUD_DEVICE_CODE]
            self._cloud_active = True
            self._modbus_enabled = entry.data.get(CONF_MODBUS_ENABLED, False)
            self._modbus_connection_type = entry.data.get(
                CONF_MODBUS_CONNECTION_TYPE, CONNECTION_TCP
            )

        # ── TCP raw socket state (tablet-synchronized) ─────────────────────────
        self._tcp_reader: asyncio.StreamReader | None = None
        self._tcp_writer: asyncio.StreamWriter | None = None
        self._tcp_buf: bytes = b""
        self._tx_counter: int = 0

        # Serializes ALL bus access so reads and writes never race on the socket.
        # Initialized lazily in _async_connect_tcp (needs running event loop).
        self._bus_lock: asyncio.Lock | None = None

        # Number of pending write operations. When > 0, the periodic read loop
        # yields the lock immediately after the current batch so writes get
        # the next free window without waiting a full update cycle.
        self._write_pending: int = 0

        # Adaptive tablet detection
        self._tablet_seen: bool = False
        self._consecutive_no_tablet: int = 0

        # Guards against overlapping snapshot consolidation runs.
        self._consolidating: bool = False

        # Serial pymodbus client
        self._serial_client: ModbusSerialClient | None = None
        # ESP32 pymodbus TCP client (proxy has its own bus, no tablet sharing)
        self._esp32_client: ModbusTcpClient | None = None

        # Determine which host/port/serial to use for Modbus.
        # For cloud-primary + Modbus-backup the same entry keys are used.
        # Options take precedence over data so the connection details (e.g. a
        # changed ESP32/DR164 IP) can be updated after initial setup.
        def _opt(key: str, default: Any) -> Any:
            return entry.options.get(key, entry.data.get(key, default))

        modbus_type = (
            self._modbus_connection_type
            if self._connection_type == CONNECTION_CLOUD
            else self._connection_type
        )
        if modbus_type == CONNECTION_SERIAL:
            self._serial_port = _opt(CONF_SERIAL_PORT, "")
            self._baudrate = _opt(CONF_BAUDRATE, DEFAULT_BAUDRATE)
        elif modbus_type in (CONNECTION_TCP, CONNECTION_ESP32):
            self._host = _opt(CONF_HOST, "")
            self._tcp_port = _opt(CONF_TCP_PORT, 502)

    @property
    def _effective_modbus_type(self) -> str:
        """Return the Modbus transport actually in use.

        When cloud is the primary connection, Modbus runs as backup/extension
        and its transport is stored in _modbus_connection_type. Otherwise the
        primary connection type is the Modbus transport.
        """
        return (
            self._modbus_connection_type
            if self._connection_type == CONNECTION_CLOUD
            else self._connection_type
        )

    # ── Shared register processing ──

    @staticmethod
    def _process_registers(
        data: dict[str, Any], start_addr: int, registers: list[int],
    ) -> None:
        """Apply scaling, sign handling, and store in data dict."""
        for i, raw in enumerate(registers):
            addr = start_addr + i
            if addr not in _ADDR_MAP:
                continue
            if raw in SENSOR_DISCONNECTED:
                continue
            dict_key, reg_info = _ADDR_MAP[addr]
            scale = reg_info.get("scale", 1)
            if reg_info.get("signed", True) and raw > 32767:
                raw = raw - 65536
            data[dict_key][addr] = raw * scale

    # ══════════════════════════════════════════════════════════════════════
    # TCP: Raw socket with tablet-synchronized bus-sharing
    # ══════════════════════════════════════════════════════════════════════

    @staticmethod
    def _build_tcp_read(
        tx_id: int, slave: int, fc: int, start: int, count: int,
    ) -> bytes:
        """Build a Modbus TCP read request frame (FC03/FC04)."""
        pdu = struct.pack(">BHH", fc, start, count)
        mbap = struct.pack(">HHHB", tx_id, 0, len(pdu) + 1, slave)
        return mbap + pdu

    @staticmethod
    def _build_tcp_write_register(
        tx_id: int, slave: int, address: int, value: int,
    ) -> bytes:
        """Build a Modbus TCP FC06 (write single register) frame."""
        pdu = struct.pack(">BHH", 6, address, value)
        mbap = struct.pack(">HHHB", tx_id, 0, len(pdu) + 1, slave)
        return mbap + pdu

    @staticmethod
    def _build_tcp_write_coil(
        tx_id: int, slave: int, address: int, value: bool,
    ) -> bytes:
        """Build a Modbus TCP FC05 (write single coil) frame."""
        coil_value = 0xFF00 if value else 0x0000
        pdu = struct.pack(">BHH", 5, address, coil_value)
        mbap = struct.pack(">HHHB", tx_id, 0, len(pdu) + 1, slave)
        return mbap + pdu

    @staticmethod
    def _parse_tcp_frames(data: bytes) -> tuple[list[dict], bytes]:
        """Parse complete Modbus TCP frames. Returns (frames, leftover_bytes)."""
        frames: list[dict] = []
        pos = 0
        while pos + 9 <= len(data):
            tx_id = struct.unpack_from(">H", data, pos)[0]
            protocol = struct.unpack_from(">H", data, pos + 2)[0]
            length = struct.unpack_from(">H", data, pos + 4)[0]

            if protocol != 0 or length < 2 or length > 253:
                pos += 1
                continue

            total = 6 + length
            if pos + total > len(data):
                break  # incomplete frame

            fc = data[pos + 7]
            payload = data[pos + 8 : pos + total]
            frame: dict[str, Any] = {"tx_id": tx_id, "fc": fc}

            # Read response (FC03/FC04): byte_count + register data
            if fc in (3, 4) and len(payload) >= 1:
                byte_count = payload[0]
                if (
                    byte_count > 0
                    and byte_count % 2 == 0
                    and byte_count == len(payload) - 1
                ):
                    reg_count = byte_count // 2
                    values = [
                        struct.unpack_from(">H", payload, 1 + i * 2)[0]
                        for i in range(reg_count)
                        if 1 + i * 2 + 2 <= len(payload)
                    ]
                    frame["type"] = "RSP"
                    frame["reg_count"] = reg_count
                    frame["values"] = values
                else:
                    frame["type"] = "OTHER"
            # FC06 write register response: echo of address + value
            elif fc == 6 and len(payload) == 4:
                frame["type"] = "WRITE_RSP"
                frame["address"] = struct.unpack_from(">H", payload, 0)[0]
                frame["value"] = struct.unpack_from(">H", payload, 2)[0]
            # FC05 write coil response: echo of address + value
            elif fc == 5 and len(payload) == 4:
                frame["type"] = "COIL_RSP"
                frame["address"] = struct.unpack_from(">H", payload, 0)[0]
                frame["value"] = struct.unpack_from(">H", payload, 2)[0]
            else:
                frame["type"] = "OTHER"

            frames.append(frame)
            pos += total

        return frames, data[pos:]

    def _next_tx_id(self) -> int:
        """Get the next unique Modbus TCP transaction ID."""
        self._tx_counter = (self._tx_counter % 65000) + 1
        return self._tx_counter

    async def _tcp_read_available(self, timeout: float = 0.05) -> list[dict]:
        """Read all available data from TCP socket, parse into frames."""
        assert self._tcp_reader is not None
        try:
            data = await asyncio.wait_for(
                self._tcp_reader.read(4096), timeout=timeout,
            )
            if data:
                self._tcp_buf += data
        except asyncio.TimeoutError:
            pass
        frames, self._tcp_buf = self._parse_tcp_frames(self._tcp_buf)
        return frames

    async def _tcp_wait_for_cycle_end(self) -> bool:
        """Wait for the tablet's cycle-end marker (54-register FC03 response).

        The manufacturer's tablet polls the heat pump in a 7-request cycle
        every ~1.3s. The last response contains 54 registers (HR[768..821]).
        After detecting it, there is a ~400ms free window for our reads.

        Uses adaptive timeout: full timeout while detecting tablet presence,
        shorter timeout once tablet is confirmed absent (saves ~4s per update).

        Returns True if cycle end detected, False on timeout (tablet offline).
        """
        if self._consecutive_no_tablet >= _NO_TABLET_THRESHOLD:
            timeout = _NO_TABLET_TIMEOUT
        else:
            timeout = _CYCLE_DETECT_TIMEOUT

        loop = asyncio.get_running_loop()
        deadline = loop.time() + timeout
        while loop.time() < deadline:
            frames = await self._tcp_read_available(timeout=0.02)
            for f in frames:
                if (
                    f.get("type") == "RSP"
                    and f.get("reg_count") == _TABLET_CYCLE_END_REGS
                ):
                    if not self._tablet_seen:
                        _LOGGER.info("Tablet detected on RS485 bus — using synchronized reads")
                    self._tablet_seen = True
                    self._consecutive_no_tablet = 0
                    return True

        self._consecutive_no_tablet += 1
        if self._consecutive_no_tablet == _NO_TABLET_THRESHOLD:
            _LOGGER.info(
                "Tablet not detected after %d attempts — switching to direct "
                "read mode (faster updates, no bus synchronization needed)",
                _NO_TABLET_THRESHOLD,
            )
            self._tablet_seen = False
        return False

    async def _tcp_send_one_read(
        self, fc: int, start: int, count: int,
    ) -> list[int] | None:
        """Send one Modbus read and wait for the matching response.

        Skips interleaved tablet traffic. Returns register values if count
        matches, None on timeout or count mismatch (collision corruption).
        """
        assert self._tcp_writer is not None
        tx_id = self._next_tx_id()
        frame = self._build_tcp_read(tx_id, self._slave_id, fc, start, count)
        self._tcp_writer.write(frame)
        await self._tcp_writer.drain()

        loop = asyncio.get_running_loop()
        deadline = loop.time() + _SINGLE_READ_TIMEOUT
        while loop.time() < deadline:
            frames = await self._tcp_read_available(timeout=0.02)
            for f in frames:
                if f.get("tx_id") == tx_id and f.get("type") == "RSP":
                    if f.get("reg_count") == count:
                        return f["values"]
                    _LOGGER.debug(
                        "Count mismatch FC%d [%d]: got %d, expected %d",
                        fc, start, f.get("reg_count"), count,
                    )
                    return None
        return None

    async def _async_connect_tcp(self) -> None:
        """Ensure a live TCP connection to the DR164 gateway."""
        if self._tcp_writer is not None:
            try:
                # Lightweight liveness check
                self._tcp_writer.write(b"")
                await self._tcp_writer.drain()
                return
            except (OSError, ConnectionError):
                await self._async_disconnect_tcp()

        _LOGGER.debug("Opening TCP connection to %s:%s", self._host, self._tcp_port)
        self._tcp_reader, self._tcp_writer = await asyncio.open_connection(
            self._host, self._tcp_port,
        )
        self._tcp_buf = b""
        # Create lock here so it's always bound to the running event loop.
        if self._bus_lock is None:
            self._bus_lock = asyncio.Lock()

        # Send probe to activate DR164's TCP-to-RS485 bridge
        tx_id = self._next_tx_id()
        probe = self._build_tcp_read(tx_id, self._slave_id, 3, 768, 1)
        self._tcp_writer.write(probe)
        await self._tcp_writer.drain()
        # Drain probe response and any buffered tablet traffic
        await self._tcp_read_available(timeout=0.5)

    async def _async_disconnect_tcp(self) -> None:
        """Close the TCP connection."""
        if self._tcp_writer:
            try:
                self._tcp_writer.close()
                await self._tcp_writer.wait_closed()
            except Exception:  # noqa: BLE001
                pass
        self._tcp_reader = None
        self._tcp_writer = None
        self._tcp_buf = b""

    async def _async_read_all_registers_tcp(self) -> dict[str, Any]:
        """Read all registers via TCP with tablet-synchronized bus-sharing.

        Strategy proven by bus_test_synced3.py (12/12 OK, 100% success):
        1. Sync to tablet cycle end (54-reg response marker)
        2. Read sequentially: one request at a time, FC04 first
        3. Count-validate each response (reject count mismatches)
        4. Retry failed reads in the next tablet cycle (max 3 attempts)

        When tablet is absent, uses direct reads with shorter timeouts.
        Yields the bus lock immediately if a write is pending so user
        actions are not delayed by a full update cycle.
        """
        await self._async_connect_tcp()
        assert self._bus_lock is not None

        async with self._bus_lock:
            data: dict[str, Any] = {
                "holding": {},
                "input": {},
                "coil": {},
                "discrete": {},
            }

            # Track pending reads: index → attempt count
            pending: dict[int, int] = {i: 0 for i in range(len(_TCP_READ_GROUPS))}
            results: dict[int, list[int]] = {}
            max_cycles = _MAX_READ_RETRIES * 2  # Safety limit

            for _cycle in range(max_cycles):
                if not pending:
                    break

                # Yield to pending writes: release the lock, sleep one scheduler
                # tick so the write can acquire it, then re-acquire for next batch.
                if self._write_pending > 0:
                    _LOGGER.debug(
                        "Write pending — yielding bus lock (%d groups remain)",
                        len(pending),
                    )
                    break

                synced = await self._tcp_wait_for_cycle_end()
                if synced:
                    _LOGGER.debug(
                        "Tablet cycle end → reading %d groups", len(pending),
                    )
                else:
                    _LOGGER.debug(
                        "Direct read mode → reading %d groups (tablet %s)",
                        len(pending),
                        "absent" if not self._tablet_seen else "missed",
                    )

                completed: list[int] = []
                for idx in sorted(pending.keys()):
                    # Re-check write_pending between each register group
                    if self._write_pending > 0:
                        _LOGGER.debug("Write pending mid-cycle — stopping reads early")
                        break
                    fc, start, count = _TCP_READ_GROUPS[idx]
                    pending[idx] += 1

                    values = await self._tcp_send_one_read(fc, start, count)
                    if values is not None:
                        results[idx] = values
                        completed.append(idx)
                    elif pending[idx] >= _MAX_READ_RETRIES:
                        _LOGGER.warning(
                            "FC%d [%d] x%d failed after %d attempts",
                            fc, start, count, _MAX_READ_RETRIES,
                        )
                        completed.append(idx)
                    else:
                        _LOGGER.debug(
                            "FC%d [%d] x%d attempt %d failed, will retry",
                            fc, start, count, pending[idx],
                        )

                for idx in completed:
                    del pending[idx]

            # Process all successful results
            for idx, values in results.items():
                _fc, start, _count = _TCP_READ_GROUPS[idx]
                self._process_registers(data, start, values)

            if pending:
                _LOGGER.debug(
                    "Deferred %d register groups (write pending or max retries)",
                    len(pending),
                )

            return data

    async def _tcp_send_write_and_wait(
        self, frame: bytes, tx_id: int, expected_type: str,
    ) -> dict | None:
        """Send a write frame and wait for the matching response.

        Acquires the bus lock so reads and writes never race on the socket.
        Syncs to the tablet cycle end inside the lock.
        """
        assert self._tcp_writer is not None
        assert self._bus_lock is not None

        self._write_pending += 1
        try:
            async with self._bus_lock:
                # Sync to tablet cycle to avoid bus collision
                await self._tcp_wait_for_cycle_end()

                self._tcp_writer.write(frame)
                await self._tcp_writer.drain()

                loop = asyncio.get_running_loop()
                deadline = loop.time() + _SINGLE_READ_TIMEOUT
                while loop.time() < deadline:
                    frames = await self._tcp_read_available(timeout=0.02)
                    for f in frames:
                        if f.get("tx_id") == tx_id and f.get("type") == expected_type:
                            return f
                return None
        finally:
            self._write_pending -= 1

    # ══════════════════════════════════════════════════════════════════════
    # Serial: Standard pymodbus client (no tablet sharing needed)
    # ══════════════════════════════════════════════════════════════════════

    def _get_serial_client(self) -> ModbusSerialClient:
        """Get or create the serial Modbus client."""
        if self._serial_client is None or not self._serial_client.connected:
            self._serial_client = ModbusSerialClient(
                port=self._serial_port,
                baudrate=self._baudrate,
                stopbits=1,
                bytesize=8,
                parity="N",
                timeout=5,
            )
            if not self._serial_client.connect():
                raise ConnectionError(
                    f"Cannot open serial port {self._serial_port}"
                )
        return self._serial_client

    def _read_all_registers_serial(self) -> dict[str, Any]:
        """Read all registers via serial (standard pymodbus)."""
        client = self._get_serial_client()
        data: dict[str, Any] = {
            "holding": {},
            "input": {},
            "coil": {},
            "discrete": {},
        }

        for start_addr, count in _HOLDING_READ_GROUPS:
            try:
                result = client.read_holding_registers(
                    start_addr, count=count, device_id=self._slave_id,
                )
                if result.isError():
                    _LOGGER.debug("Error reading HR[%d..%d]: %s", start_addr, start_addr + count - 1, result)
                    continue
                self._process_registers(data, start_addr, result.registers)
            except ModbusException as err:
                _LOGGER.debug("Modbus error HR[%d..%d]: %s", start_addr, start_addr + count - 1, err)

        for start_addr, count in _INPUT_READ_GROUPS:
            try:
                result = client.read_input_registers(
                    start_addr, count=count, device_id=self._slave_id,
                )
                if result.isError():
                    _LOGGER.debug("Error reading IR[%d..%d]: %s", start_addr, start_addr + count - 1, result)
                    continue
                self._process_registers(data, start_addr, result.registers)
            except ModbusException as err:
                _LOGGER.debug("Modbus error IR[%d..%d]: %s", start_addr, start_addr + count - 1, err)

        return data

    def _reset_serial_client(self) -> None:
        """Force-close the serial client."""
        if self._serial_client:
            try:
                self._serial_client.close()
            except Exception:  # noqa: BLE001
                pass
            self._serial_client = None

    # ══════════════════════════════════════════════════════════════════════
    # ESP32: Standard pymodbus TCP client (proxy owns the bus, no tablet)
    # ══════════════════════════════════════════════════════════════════════

    def _get_esp32_client(self) -> ModbusTcpClient:
        """Get or create the ESP32 Modbus-TCP client."""
        if self._esp32_client is None or not self._esp32_client.connected:
            self._esp32_client = ModbusTcpClient(
                host=self._host,
                port=self._tcp_port,
                timeout=5,
            )
            if not self._esp32_client.connect():
                raise ConnectionError(
                    f"Cannot connect to ESP32 proxy {self._host}:{self._tcp_port}"
                )
        return self._esp32_client

    def _read_all_registers_esp32(self) -> dict[str, Any]:
        """Read all registers via ESP32 proxy (standard pymodbus TCP)."""
        client = self._get_esp32_client()
        data: dict[str, Any] = {
            "holding": {},
            "input": {},
            "coil": {},
            "discrete": {},
        }

        for start_addr, count in _HOLDING_READ_GROUPS:
            try:
                result = client.read_holding_registers(
                    start_addr, count=count, device_id=self._slave_id,
                )
                if result.isError():
                    _LOGGER.debug("Error reading HR[%d..%d]: %s", start_addr, start_addr + count - 1, result)
                    continue
                self._process_registers(data, start_addr, result.registers)
            except ModbusException as err:
                _LOGGER.debug("Modbus error HR[%d..%d]: %s", start_addr, start_addr + count - 1, err)

        for start_addr, count in _INPUT_READ_GROUPS:
            try:
                result = client.read_input_registers(
                    start_addr, count=count, device_id=self._slave_id,
                )
                if result.isError():
                    _LOGGER.debug("Error reading IR[%d..%d]: %s", start_addr, start_addr + count - 1, result)
                    continue
                self._process_registers(data, start_addr, result.registers)
            except ModbusException as err:
                _LOGGER.debug("Modbus error IR[%d..%d]: %s", start_addr, start_addr + count - 1, err)

        return data

    def _reset_esp32_client(self) -> None:
        """Force-close the ESP32 TCP client."""
        if self._esp32_client:
            try:
                self._esp32_client.close()
            except Exception:  # noqa: BLE001
                pass
            self._esp32_client = None

    # ══════════════════════════════════════════════════════════════════════
    # Public API
    # ══════════════════════════════════════════════════════════════════════

    async def _async_offload(self, data: dict[str, Any]) -> None:
        """Optionally push the register snapshot to a NAS endpoint for later decode.

        Disabled unless CONF_OFFLOAD_ENABLED is true and CONF_OFFLOAD_URL is set.
        Failures are logged and swallowed so they never break HA updates.
        """
        options = self.config_entry.options
        if not options.get(CONF_OFFLOAD_ENABLED):
            return
        url = options.get(CONF_OFFLOAD_URL, "").strip()
        if not url:
            return
        payload = {
            "ts": dt_util.utcnow().isoformat(),
            "host": getattr(self, "_host", None),
            "slave_id": self._slave_id,
            "holding": {str(k): v for k, v in data.get("holding", {}).items()},
            "input": {str(k): v for k, v in data.get("input", {}).items()},
        }
        # Local directory (NFS/CIFS mount or HA /share, /media) → write a file.
        if url.startswith("file://") or url.startswith("/"):
            path = url[7:] if url.startswith("file://") else url
            try:
                written = await self.hass.async_add_executor_job(
                    self._offload_to_file, path, payload
                )
                _LOGGER.debug("Offload wrote snapshot to %s", written)
            except Exception as err:  # noqa: BLE001
                _LOGGER.warning("Offload to %s failed: %s", path, err)
            return
        try:
            session = async_get_clientsession(self.hass)
            async with session.post(url, json=payload, timeout=5) as resp:
                if resp.status >= 400:
                    _LOGGER.debug("Offload POST %s returned %s", url, resp.status)
        except Exception as err:  # noqa: BLE001
            _LOGGER.debug("Offload to %s failed: %s", url, err)

    @staticmethod
    def _offload_to_file(directory: str, payload: dict[str, Any]) -> str:
        """Write the snapshot as a timestamped JSON file in a local directory.

        Returns the full path written. Raises on permission/IO errors so the
        caller can surface them.
        """
        import json
        import os

        os.makedirs(directory, exist_ok=True)
        name = f"snap_{payload['ts'].replace(':', '').replace('.', '')}.json"
        full = os.path.join(directory, name)
        with open(full, "w", encoding="utf-8") as fh:
            json.dump(payload, fh)
        return full

    def _offload_local_dir(self) -> str | None:
        """Return the local offload directory, or None if offload isn't local.

        Snapshots are only consolidated when the offload target is a local path
        (NFS/CIFS mount, or HA /share, /media). HTTP targets and disabled
        offload have nothing to consolidate.
        """
        options = self.config_entry.options
        if not options.get(CONF_OFFLOAD_ENABLED):
            return None
        url = options.get(CONF_OFFLOAD_URL, "").strip()
        if not url:
            return None
        if url.startswith("file://"):
            return url[7:]
        if url.startswith("/"):
            return url
        return None

    async def async_consolidate_snapshots(self, _now: Any = None) -> None:
        """Merge offloaded snap_*.json files into snapshots.db, then delete them.

        Runs unconditionally on a fixed schedule whenever offload writes to a
        local directory. Failures are logged and swallowed so they never affect
        HA. An in-flight guard prevents overlapping runs.
        """
        directory = self._offload_local_dir()
        if not directory or self._consolidating:
            return
        self._consolidating = True
        try:
            max_mb = self.config_entry.options.get(
                CONF_OFFLOAD_DB_MAX_MB, DEFAULT_OFFLOAD_DB_MAX_MB
            )
            max_bytes = int(max_mb) * 1024 * 1024 if max_mb else 0
            merged, readings, pruned = await self.hass.async_add_executor_job(
                self._consolidate_dir, directory, max_bytes
            )
            if merged:
                _LOGGER.info(
                    "Consolidated %d snapshot(s) (%d readings) into %s",
                    merged, readings, CONSOLIDATE_DB_NAME,
                )
            if pruned:
                _LOGGER.info(
                    "Pruned %d oldest snapshot(s) to keep %s under %d MB",
                    pruned, CONSOLIDATE_DB_NAME, int(max_mb),
                )
        except Exception as err:  # noqa: BLE001
            _LOGGER.warning("Snapshot consolidation failed: %s", err)
        finally:
            self._consolidating = False

    @staticmethod
    def _consolidate_dir(directory: str, max_bytes: int = 0) -> tuple[int, int, int]:
        """Blocking: ingest all snap_*.json in *directory* into snapshots.db.

        Returns (files_merged, readings_stored, snapshots_pruned). Each file is
        committed and deleted individually so an interruption never loses data
        or re-ingests. Uses the rollback journal (not WAL) because the database
        typically lives on a network share where WAL is unsupported.

        When *max_bytes* > 0 the oldest snapshots are pruned after appending
        until the database file fits within the limit. auto_vacuum=FULL keeps
        the file from growing back, so the size cap is actually enforced.
        """
        import glob
        import json
        import os
        import sqlite3

        files = sorted(glob.glob(os.path.join(directory, "snap_*.json")))
        if not files and max_bytes <= 0:
            return (0, 0, 0)

        db_path = os.path.join(directory, CONSOLIDATE_DB_NAME)
        conn = sqlite3.connect(db_path)
        merged = 0
        readings = 0
        pruned = 0
        try:
            conn.execute("PRAGMA journal_mode=DELETE;")
            conn.execute("PRAGMA synchronous=NORMAL;")
            # Enable auto_vacuum so pruning actually shrinks the file. Converting
            # an existing non-auto_vacuum database requires a one-time VACUUM.
            if max_bytes > 0:
                if conn.execute("PRAGMA auto_vacuum").fetchone()[0] != 1:
                    conn.execute("PRAGMA auto_vacuum=FULL;")
                    conn.execute("VACUUM;")
            conn.executescript(_CONSOLIDATE_SCHEMA)
            for path in files:
                try:
                    with open(path, "r", encoding="utf-8") as fh:
                        payload = json.load(fh)
                except (OSError, json.JSONDecodeError):
                    continue
                cur = conn.execute(
                    "INSERT INTO snapshots (ts, host, slave_id) VALUES (?, ?, ?)",
                    (payload.get("ts"), payload.get("host"), payload.get("slave_id")),
                )
                snapshot_id = cur.lastrowid
                rows: list[tuple[int, str, int, Any]] = []
                for reg_type in ("holding", "input"):
                    for addr, value in (payload.get(reg_type) or {}).items():
                        try:
                            rows.append((snapshot_id, reg_type, int(addr), value))
                        except (ValueError, TypeError):
                            continue
                if rows:
                    conn.executemany(
                        "INSERT INTO readings (snapshot_id, reg_type, address, value) "
                        "VALUES (?, ?, ?, ?)",
                        rows,
                    )
                conn.commit()
                readings += len(rows)
                merged += 1
                try:
                    os.remove(path)
                except OSError:
                    pass
            # Enforce the size cap by deleting the oldest snapshots in batches.
            if max_bytes > 0:
                while os.path.getsize(db_path) > max_bytes:
                    ids = [
                        r[0] for r in conn.execute(
                            "SELECT id FROM snapshots ORDER BY id ASC LIMIT 200"
                        ).fetchall()
                    ]
                    if not ids:
                        break
                    placeholders = ",".join("?" * len(ids))
                    conn.execute(
                        f"DELETE FROM readings WHERE snapshot_id IN ({placeholders})",
                        ids,
                    )
                    conn.execute(
                        f"DELETE FROM snapshots WHERE id IN ({placeholders})", ids
                    )
                    conn.commit()
                    pruned += len(ids)
                    if len(ids) < 200:
                        break
        finally:
            conn.close()
        return (merged, readings, pruned)

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch data from the heat pump (cloud, Modbus, or both)."""
        if self._connection_type == CONNECTION_CLOUD:
            return await self._async_update_cloud()

        # ── Modbus-only path (unchanged) ──────────────────────────────────────
        try:
            if self._connection_type == CONNECTION_TCP:
                data = await self._async_read_all_registers_tcp()
            elif self._connection_type == CONNECTION_ESP32:
                data = await self.hass.async_add_executor_job(
                    self._read_all_registers_esp32,
                )
            else:
                data = await self.hass.async_add_executor_job(
                    self._read_all_registers_serial,
                )
            await self._async_offload(data)
            return data
        except ConnectionError as err:
            self._reset_modbus_client()
            raise UpdateFailed(f"Connection error: {err}") from err
        except Exception as err:
            self._reset_modbus_client()
            raise UpdateFailed(f"Error communicating with heat pump: {err}") from err

    async def _async_update_cloud(self) -> dict[str, Any]:
        """Poll the cloud API and optionally the Modbus backup."""
        data: dict[str, Any] = {
            "holding": {}, "input": {}, "coil": {}, "discrete": {}, "cloud": {},
        }

        # ── Cloud read ────────────────────────────────────────────────────────
        assert self._cloud is not None
        if self._cloud_active:
            try:
                if not await self._cloud.is_session_valid():
                    await self._cloud.authenticate()
                cloud_values = await self._cloud.fetch_all_params(self._cloud_device_code)
                data["cloud"] = cloud_values
                self._cloud_failures = 0
            except (CloudAuthError, CloudSessionError):
                # Try a single re-authentication before giving up.
                try:
                    await self._cloud.authenticate()
                    cloud_values = await self._cloud.fetch_all_params(self._cloud_device_code)
                    data["cloud"] = cloud_values
                    self._cloud_failures = 0
                except Exception as err:  # noqa: BLE001
                    self._cloud_failures += 1
                    _LOGGER.warning(
                        "Cloud re-auth failed (%d/%d): %s",
                        self._cloud_failures, CLOUD_FAILURE_THRESHOLD, err,
                    )
            except Exception as err:  # noqa: BLE001
                self._cloud_failures += 1
                _LOGGER.warning(
                    "Cloud poll failed (%d/%d): %s",
                    self._cloud_failures, CLOUD_FAILURE_THRESHOLD, err,
                )

            if self._cloud_failures >= CLOUD_FAILURE_THRESHOLD:
                self._cloud_active = False
                _LOGGER.warning(
                    "Cloud unreachable after %d attempts — falling back to Modbus",
                    CLOUD_FAILURE_THRESHOLD,
                )
        else:
            # Attempt to restore the cloud connection in the background.
            try:
                await self._cloud.authenticate()
                self._cloud_active = True
                self._cloud_failures = 0
                _LOGGER.info("Cloud connection restored")
            except Exception:  # noqa: BLE001
                pass  # Will retry next cycle

        # ── Device on/off + operation mode (getDeviceDetailV3) ────────────────
        # These control values are not in paramListV3; merge them into the
        # cloud data dict using their own cloud addresses (e.g. 1017, 1021).
        if data["cloud"]:
            try:
                state = await self._cloud.fetch_device_state(self._cloud_device_code)
                data["cloud"].update(state)
            except Exception as err:  # noqa: BLE001
                _LOGGER.debug("Device state fetch failed: %s", err)

        # ── Modbus backup read ────────────────────────────────────────────────
        if self._modbus_enabled:
            try:
                mtype = self._modbus_connection_type
                if mtype == CONNECTION_TCP:
                    modbus_data = await self._async_read_all_registers_tcp()
                elif mtype == CONNECTION_ESP32:
                    modbus_data = await self.hass.async_add_executor_job(
                        self._read_all_registers_esp32,
                    )
                else:
                    modbus_data = await self.hass.async_add_executor_job(
                        self._read_all_registers_serial,
                    )
                data["holding"].update(modbus_data["holding"])
                data["input"].update(modbus_data["input"])
                data["coil"].update(modbus_data.get("coil", {}))
            except Exception as err:  # noqa: BLE001
                if not self._cloud_active and not data["cloud"]:
                    raise UpdateFailed(
                        f"Both cloud and Modbus unavailable: {err}"
                    ) from err
                _LOGGER.debug("Modbus backup read failed (cloud still active): %s", err)
                self._reset_modbus_client()
        elif not data["cloud"] and not self._cloud_active:
            raise UpdateFailed("Cloud unavailable and no Modbus backup configured")

        await self._async_offload(data)
        return data

    def _reset_modbus_client(self) -> None:
        """Disconnect whichever Modbus client is active."""
        conn = (
            self._modbus_connection_type
            if self._connection_type == CONNECTION_CLOUD
            else self._connection_type
        )
        if conn == CONNECTION_TCP:
            self.hass.loop.create_task(self._async_disconnect_tcp())
        elif conn == CONNECTION_ESP32:
            self._reset_esp32_client()
        else:
            self._reset_serial_client()

    async def async_cloud_set_value(self, address: int, value: int) -> None:
        """Write a parameter via the cloud API and trigger a data refresh."""
        if self._cloud is None or not self._cloud_active:
            raise RuntimeError("Cloud connection is not available")
        try:
            if not await self._cloud.is_session_valid():
                await self._cloud.authenticate()
            await self._cloud.set_param(self._cloud_device_code, address, value)
        except (CloudAuthError, CloudSessionError):
            await self._cloud.authenticate()
            await self._cloud.set_param(self._cloud_device_code, address, value)
        await self.async_request_refresh()

    async def async_cloud_set_switch(self, address: int, on: bool) -> None:
        """Set an on/off switch address via the cloud API (updateSwitchSate)."""
        if self._cloud is None or not self._cloud_active:
            raise RuntimeError("Cloud connection is not available")
        try:
            if not await self._cloud.is_session_valid():
                await self._cloud.authenticate()
            await self._cloud.toggle_switch(self._cloud_device_code, address, on)
        except (CloudAuthError, CloudSessionError):
            await self._cloud.authenticate()
            await self._cloud.toggle_switch(self._cloud_device_code, address, on)
        await self.async_request_refresh()

    def _write_with_reconnect(self, write_fn) -> None:
        """Run a pymodbus write, reconnecting once on a stale connection.

        ESP32/serial clients keep the socket open between updates. The ESP32
        proxy closes idle TCP connections after ~2s, so a write on a stale
        socket fails with ConnectionException ("connection unexpectedly
        closed"). Reads auto-recover, writes did not. Reset the client and
        retry once so the action succeeds transparently.
        """
        try:
            write_fn()
        except (ConnectionException, ConnectionError, OSError) as err:
            _LOGGER.debug("Write failed (%s) — reconnecting and retrying", err)
            if self._effective_modbus_type == CONNECTION_ESP32:
                self._reset_esp32_client()
            else:
                self._reset_serial_client()
            write_fn()

    async def async_write_register(self, address: int, value: int) -> None:
        """Write a value to a holding register (FC06).

        When cloud is primary the effective Modbus type comes from
        _modbus_connection_type (set when Modbus backup is configured).
        """
        effective = self._effective_modbus_type
        if effective == CONNECTION_TCP:
            await self._async_connect_tcp()
            last_err: str = "unknown"
            for attempt in range(1, _MAX_READ_RETRIES + 1):
                tx_id = self._next_tx_id()
                frame = self._build_tcp_write_register(
                    tx_id, self._slave_id, address, value,
                )
                resp = await self._tcp_send_write_and_wait(frame, tx_id, "WRITE_RSP")
                if resp is None:
                    last_err = f"timeout (attempt {attempt}/{_MAX_READ_RETRIES})"
                    _LOGGER.debug("Write HR[%d] %s", address, last_err)
                    continue
                if resp.get("address") != address or resp.get("value") != value:
                    last_err = f"echo mismatch (attempt {attempt}/{_MAX_READ_RETRIES})"
                    _LOGGER.debug("Write HR[%d] %s", address, last_err)
                    continue
                break  # success
            else:
                raise ModbusException(f"Failed to write HR[{address}] after {_MAX_READ_RETRIES} attempts: {last_err}")
        else:
            def _write() -> None:
                client = (
                    self._get_esp32_client()
                    if effective == CONNECTION_ESP32
                    else self._get_serial_client()
                )
                result = client.write_register(
                    address, value, device_id=self._slave_id,
                )
                if result.isError():
                    raise ModbusException(f"Failed to write register {address}")

            await self.hass.async_add_executor_job(
                self._write_with_reconnect, _write,
            )

        await self.async_request_refresh()

    async def async_write_coil(self, address: int, value: bool) -> None:
        """Write a value to a coil (FC05, pulse-based)."""
        effective = self._effective_modbus_type
        if effective == CONNECTION_TCP:
            await self._async_connect_tcp()
            last_err: str = "unknown"
            for attempt in range(1, _MAX_READ_RETRIES + 1):
                tx_id = self._next_tx_id()
                frame = self._build_tcp_write_coil(
                    tx_id, self._slave_id, address, value,
                )
                resp = await self._tcp_send_write_and_wait(frame, tx_id, "COIL_RSP")
                if resp is None:
                    last_err = f"timeout (attempt {attempt}/{_MAX_READ_RETRIES})"
                    _LOGGER.debug("Write coil[%d] %s", address, last_err)
                    continue
                break  # success
            else:
                raise ModbusException(f"Failed to write coil {address} after {_MAX_READ_RETRIES} attempts: {last_err}")
        else:
            def _write() -> None:
                client = (
                    self._get_esp32_client()
                    if effective == CONNECTION_ESP32
                    else self._get_serial_client()
                )
                result = client.write_coil(
                    address, value, device_id=self._slave_id,
                )
                if result.isError():
                    raise ModbusException(f"Failed to write coil {address}")

            await self.hass.async_add_executor_job(
                self._write_with_reconnect, _write,
            )

        await self.async_request_refresh()

    async def async_close(self) -> None:
        """Close all connections (called on integration unload)."""
        # Determine which Modbus transport is active (primary or backup)
        active_modbus = (
            self._modbus_connection_type
            if self._connection_type == CONNECTION_CLOUD
            else self._connection_type
        )
        if active_modbus == CONNECTION_TCP:
            await self._async_disconnect_tcp()
        elif active_modbus == CONNECTION_ESP32:
            if self._esp32_client:
                await self.hass.async_add_executor_job(self._esp32_client.close)
                self._esp32_client = None
        elif self._serial_client:
            await self.hass.async_add_executor_job(self._serial_client.close)
            self._serial_client = None
