"""Shared helpers for the exploration scripts.

The scripts load the library straight from the integration folder, so they run
without Home Assistant installed.
"""
import asyncio
import pathlib
import re
import sys
import time
import zlib

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "custom_components" / "gmscreen"))

from api import DEFAULT_PORT, GMScreenClient  # noqa: E402
from api.protocol import split_replies  # noqa: E402


def parse_target(arg: str) -> tuple[str, int]:
    """'192.168.1.5' or '192.168.1.5:20000'."""
    host, _, port = arg.partition(":")
    return host, int(port) if port else DEFAULT_PORT


async def open_session(target: str) -> GMScreenClient:
    """Connect and take the socket away from the library's reader task, so the script
    can read raw bytes itself."""
    host, port = parse_target(target)
    client = GMScreenClient(host, port)
    await client.connect()
    client._read_task.cancel()          # noqa: SLF001 - deliberate: raw access for exploration
    return client


async def collect(reader: asyncio.StreamReader, quiet: float, maximum: float) -> tuple[bytes, bool]:
    """Read until the box has been silent for `quiet` seconds (or `maximum` passed).
    Returns (bytes, closed_by_box)."""
    buf, start, last = b"", time.time(), time.time()
    while time.time() - start < maximum and time.time() - last < quiet:
        try:
            chunk = await asyncio.wait_for(reader.read(65536), 0.15)
        except asyncio.TimeoutError:
            continue
        if not chunk:
            return buf, True
        buf += chunk
        last = time.time()
    return buf, False


def describe(buf: bytes) -> tuple[list[tuple[int, str]], bytes]:
    """Reply frames as (request id, compact text). Empty frames show as '<empty>'."""
    frames, rest = split_replies(buf)
    out = []
    for rid, body in frames:
        if not body:
            out.append((rid, "<empty>"))
            continue
        try:
            text = zlib.decompressobj().decompress(body).decode("utf-8", "replace")
        except zlib.error:
            text = f"<undecodable {len(body)} bytes>"
        out.append((rid, re.sub(r"\s+", " ", text)))
    return out, rest
