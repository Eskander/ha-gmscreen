"""Asyncio client for boxes that speak the G-MScreen protocol."""
from __future__ import annotations

import asyncio
import contextlib
import uuid

from .const import BEACON_SIZE, DEFAULT_PORT, Key, keymap_for
from .protocol import (BoxInfo, ProtocolError, decode_body, handshake_request, key_request,
                       parse_beacon, request_body, split_replies)


class GMScreenError(Exception):
    pass


class BoxFullError(GMScreenError):
    """The box already has its maximum number of remote clients."""


class GMScreenClient:
    def __init__(self, host: str, port: int = DEFAULT_PORT, *,
                 client_uuid: str | None = None, device_name: str = "HomeAssistant",
                 timeout: float = 10.0) -> None:
        self.host = host
        self.port = port
        # The box appears to keep one slot per client UUID, so it must be stable across
        # runs.  Default: a fixed UUID derived from name and host.
        self.client_uuid = client_uuid or str(
            uuid.uuid5(uuid.NAMESPACE_URL, f"gmscreen:{device_name}:{host}"))
        self.device_name = device_name
        self.timeout = timeout
        self.info: BoxInfo | None = None
        self._reader: asyncio.StreamReader | None = None
        self._writer: asyncio.StreamWriter | None = None
        self._read_task: asyncio.Task | None = None
        self._pending: dict[int, asyncio.Future] = {}
        self._lock = asyncio.Lock()

    @property
    def connected(self) -> bool:
        return (self._writer is not None and not self._writer.is_closing()
                and self._read_task is not None and not self._read_task.done())

    # ---- session -------------------------------------------------------------------

    async def connect(self, *, allow_full: bool = False, full_retries: int = 4,
                      full_delay: float = 3.0) -> BoxInfo:
        """Open a session.  If the box reports it is full, wait and retry; with
        allow_full=True proceed anyway."""
        await self.close()
        for attempt in range(full_retries + 1):
            try:
                self._reader, self._writer = await asyncio.wait_for(
                    asyncio.open_connection(self.host, self.port), self.timeout)
                self._writer.write(handshake_request(self.device_name, self.client_uuid))
                await self._writer.drain()
                raw = await asyncio.wait_for(self._reader.readexactly(BEACON_SIZE), self.timeout)
                info = parse_beacon(raw, self.host)
            except (OSError, asyncio.TimeoutError, asyncio.IncompleteReadError, ProtocolError) as err:
                await self.close()
                raise GMScreenError(f"handshake with {self.host}:{self.port} failed: {err!r}") from err
            if info.full and not allow_full:
                await self.close()
                if attempt < full_retries:
                    await asyncio.sleep(full_delay)
                    continue
                raise BoxFullError("box reports it is full")
            self.info = info
            self._read_task = asyncio.create_task(self._read_loop(self._reader))
            return info
        raise BoxFullError("box reports it is full")

    async def _read_loop(self, reader: asyncio.StreamReader) -> None:
        """Parse reply frames and hand them to whoever asked for that request id."""
        buf = b""
        try:
            while chunk := await reader.read(65536):
                buf += chunk
                frames, buf = split_replies(buf)
                for rid, body in frames:
                    data = decode_body(body)
                    fut = self._pending.get(rid)
                    # empty frames are bare acknowledgements; keep waiting for data
                    if data is not None and fut is not None and not fut.done():
                        fut.set_result(data)
        except Exception:  # noqa: BLE001 - any failure just ends the session
            pass
        finally:
            for fut in self._pending.values():
                if not fut.done():
                    fut.set_exception(ConnectionResetError("box closed the connection"))

    async def close(self) -> None:
        if self._read_task:
            self._read_task.cancel()
            self._read_task = None
        if self._writer:
            self._writer.close()
            with contextlib.suppress(Exception):
                await self._writer.wait_closed()
        self._reader = self._writer = None

    # ---- sending -------------------------------------------------------------------

    async def _send(self, resolve) -> None:
        """Send one key press.  Connect, resolve and write happen under one lock so
        concurrent callers never open two sessions.  A stale session is replaced and
        the press retried once."""
        for attempt in (1, 2):
            async with self._lock:
                try:
                    if not self.connected:
                        await self.connect()
                    assert self.info and self._writer
                    code = resolve(self.info)
                    self._writer.write(key_request(code, self.info.data_type))
                    await asyncio.wait_for(self._writer.drain(), self.timeout)
                    return
                except (OSError, asyncio.TimeoutError) as err:
                    await self.close()
                    if attempt == 2:
                        raise GMScreenError(f"send failed: {err!r}") from err

    async def send_code(self, code: int) -> None:
        await self._send(lambda info: code)

    async def send_key(self, key: Key | str) -> None:
        key = Key(key)

        def resolve(info: BoxInfo) -> int:
            table = keymap_for(info.platform_id)
            if key not in table:
                raise GMScreenError(f"{key.value} is not available on platform {info.platform_id}")
            return table[key]

        await self._send(resolve)

    # ---- queries -------------------------------------------------------------------

    async def request(self, rid: int, timeout: float | None = None) -> list:
        """Send a bare query and return the reply whose header carries the same id."""
        timeout = timeout or self.timeout
        for attempt in (1, 2):
            async with self._lock:
                fut: asyncio.Future | None = None
                try:
                    if not self.connected:
                        await self.connect()
                    assert self.info and self._writer
                    fut = asyncio.get_running_loop().create_future()
                    self._pending[rid] = fut
                    self._writer.write(request_body(rid, self.info.data_type))
                    await asyncio.wait_for(self._writer.drain(), self.timeout)
                    return await asyncio.wait_for(fut, timeout)
                except (OSError, asyncio.TimeoutError) as err:
                    await self.close()           # unresponsive or closed: start fresh
                    if attempt == 2:
                        raise GMScreenError(f"request {rid} failed: {err!r}") from err
                finally:
                    self._pending.pop(rid, None)
        raise GMScreenError(f"request {rid} failed")

    async def __aenter__(self) -> "GMScreenClient":
        await self.connect()
        return self

    async def __aexit__(self, *exc) -> None:
        await self.close()
