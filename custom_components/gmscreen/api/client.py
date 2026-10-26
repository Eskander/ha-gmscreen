"""Asyncio client for boxes that speak the G-MScreen protocol."""
from __future__ import annotations

import asyncio
import contextlib
import uuid

from .const import BEACON_SIZE, DEFAULT_PORT, Key, keymap_for
from .protocol import BoxInfo, ProtocolError, handshake_request, key_request, parse_beacon


class GMScreenError(Exception):
    pass


class BoxFullError(GMScreenError):
    """The box already has its maximum number of remote clients."""


class GMScreenClient:
    def __init__(self, host: str, port: int = DEFAULT_PORT, *,
                 client_uuid: str | None = None, device_name: str = "HomeAssistant",
                 timeout: float = 4.0) -> None:
        self.host = host
        self.port = port
        self.client_uuid = client_uuid or str(uuid.uuid4())
        self.device_name = device_name
        self.timeout = timeout
        self.info: BoxInfo | None = None
        self._reader: asyncio.StreamReader | None = None
        self._writer: asyncio.StreamWriter | None = None
        self._drain_task: asyncio.Task | None = None
        self._lock = asyncio.Lock()

    @property
    def connected(self) -> bool:
        return self._writer is not None and not self._writer.is_closing() \
            and self._drain_task is not None and not self._drain_task.done()

    async def connect(self) -> BoxInfo:
        await self.close()
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
        if info.full:
            await self.close()
            raise BoxFullError("box reports it is full")
        self.info = info
        self._drain_task = asyncio.create_task(self._drain())
        return info

    async def _drain(self) -> None:
        """Discard whatever the box pushes so buffers never fill; ends on disconnect."""
        assert self._reader is not None
        with contextlib.suppress(Exception):
            while await self._reader.read(4096):
                pass

    async def close(self) -> None:
        if self._drain_task:
            self._drain_task.cancel()
            self._drain_task = None
        if self._writer:
            self._writer.close()
            with contextlib.suppress(Exception):
                await self._writer.wait_closed()
        self._reader = self._writer = None

    async def _send(self, resolve) -> None:
        """Send one key press.  Connect, resolve and write happen under one lock so
        concurrent callers never open two sessions.  The box drops idle clients after
        roughly 25 s, so a stale session is replaced and the press retried once."""
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
        """Send a raw key code."""
        await self._send(lambda info: code)

    async def send_key(self, key: Key | str) -> None:
        key = Key(key)

        def resolve(info: BoxInfo) -> int:
            table = keymap_for(info.platform_id)
            if key not in table:
                raise GMScreenError(f"{key.value} is not available on platform {info.platform_id}")
            return table[key]

        await self._send(resolve)

    async def __aenter__(self) -> "GMScreenClient":
        await self.connect()
        return self

    async def __aexit__(self, *exc) -> None:
        await self.close()
