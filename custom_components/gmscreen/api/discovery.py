"""Passive discovery: boxes broadcast a beacon to UDP port 25860."""
from __future__ import annotations

import asyncio
import socket

from .const import BEACON_SIZE, DISCOVERY_PORT
from .protocol import BoxInfo, ProtocolError, parse_beacon


class _Proto(asyncio.DatagramProtocol):
    def __init__(self, found: dict[str, BoxInfo]) -> None:
        self.found = found

    def datagram_received(self, data: bytes, addr) -> None:
        if len(data) != BEACON_SIZE:
            return
        try:
            info = parse_beacon(data, addr[0])
        except ProtocolError:
            return
        self.found[info.serial] = info


async def discover(timeout: float = 6.0, port: int = DISCOVERY_PORT) -> list[BoxInfo]:
    loop = asyncio.get_running_loop()
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind(("", port))
    sock.setblocking(False)
    found: dict[str, BoxInfo] = {}
    transport, _ = await loop.create_datagram_endpoint(lambda: _Proto(found), sock=sock)
    try:
        await asyncio.sleep(timeout)
    finally:
        transport.close()
    return list(found.values())
