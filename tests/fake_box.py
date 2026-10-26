"""A fake set-top box that speaks the protocol, for tests."""
from __future__ import annotations

import asyncio
import json
import re
import struct
import zlib

import _api  # noqa: F401  (registers the gmscreen_api package)
from gmscreen_api import const, protocol


def make_beacon(*, data_type: int = 1, platform_id: int = 96, full: bool = False,
                model: bytes = b"TestBox", serial=(258, 772), ip=(192, 168, 1, 100)) -> bytes:
    """Build a beacon as it travels on the wire (obfuscated)."""
    d = bytearray(const.BEACON_SIZE)
    d[:12] = const.MAGIC
    d[12:15] = serial[0].to_bytes(3, "big")
    d[15:18] = serial[1].to_bytes(3, "big")
    d[20:20 + len(model)] = model
    d[68:72] = bytes(reversed(ip))
    d[72] = platform_id
    d[73:75] = (1, 135)                      # software version 0x0187 = 391
    d[84] = (data_type << 6) | (1 if full else 0)
    return protocol.deobfuscate(bytes(d))    # the obfuscation is its own inverse


def gcdh(rid: int, obj) -> bytes:
    """A reply frame; obj=None gives the box's zero-length acknowledgement."""
    body = b"" if obj is None else zlib.compress(json.dumps(obj, indent="\t").encode())
    return b"GCDH" + struct.pack("<III", len(body), rid, 0) + body


class FakeBox:
    def __init__(self, *, replies: dict | None = None, **beacon) -> None:
        self.beacon = make_beacon(**beacon)
        self.replies = replies or {}          # request id -> bytes to send back
        self.handshakes: list[str] = []
        self.received: list[str] = []
        self.connections = 0
        self._writers: list[asyncio.StreamWriter] = []

    async def __aenter__(self) -> "FakeBox":
        self._server = await asyncio.start_server(self._handle, "127.0.0.1", 0)
        self.port = self._server.sockets[0].getsockname()[1]
        return self

    async def __aexit__(self, *exc) -> None:
        self.drop_clients()
        self._server.close()
        await self._server.wait_closed()

    def drop_clients(self) -> None:
        """Close every open session, like the box does when a client is idle."""
        for writer in self._writers:
            writer.close()
        self._writers.clear()

    @staticmethod
    async def _read_frame(reader: asyncio.StreamReader) -> str:
        header = await reader.readexactly(15)
        assert header[:5] == b"Start" and header[12:] == b"End", header
        return (await reader.readexactly(int(header[5:12]))).decode()

    async def _handle(self, reader, writer) -> None:
        self.connections += 1
        self._writers.append(writer)
        try:
            self.handshakes.append(await self._read_frame(reader))
            writer.write(self.beacon)
            await writer.drain()
            while True:
                text = await self._read_frame(reader)
                self.received.append(text)
                if text.startswith("{"):
                    rid = int(json.loads(text)["request"])
                else:
                    rid = int(re.search(r'request="(\d+)"', text).group(1))
                reply = self.replies.get(rid)
                if reply is not None:
                    half = len(reply) // 2            # split across two packets on purpose
                    writer.write(reply[:half])
                    await writer.drain()
                    await asyncio.sleep(0.01)
                    writer.write(reply[half:])
                    await writer.drain()
        except (asyncio.IncompleteReadError, ConnectionError):
            pass
