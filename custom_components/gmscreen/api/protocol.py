"""Wire format helpers: framing, beacon decoding, request bodies."""
from __future__ import annotations

import json
import struct
import zlib
from dataclasses import dataclass
from xml.sax.saxutils import escape

from .const import BEACON_SIZE, DATA_JSON, MAGIC, XOR_KEY, REQ_HANDSHAKE, REQ_KEY


class ProtocolError(Exception):
    pass


def deobfuscate(buf: bytes) -> bytes:
    """Reverse the byte order and XOR with 0x5B (the operation is its own inverse)."""
    n = len(buf)
    out = bytearray(buf)
    for i in range(n // 2):
        j = n - 1 - i
        out[i], out[j] = buf[j] ^ XOR_KEY, buf[i] ^ XOR_KEY
    if n % 2:
        out[n // 2] ^= XOR_KEY
    return bytes(out)


def frame(payload: bytes) -> bytes:
    """'Start' + 7 digit zero padded length + 'End' + payload."""
    return b"Start" + b"%07d" % len(payload) + b"End" + payload


@dataclass
class BoxInfo:
    host: str
    serial: str
    model: str
    ip: str
    platform_id: int
    sw_version: int
    sw_sub_version: int
    customer_id: int
    model_id: int
    full: bool          # box refuses more clients
    data_type: int      # 0 = XML, 1 = JSON
    sat_enabled: bool
    dlna: bool
    ott: bool
    raw: bytes = b""


def parse_beacon(raw: bytes, host: str = "") -> BoxInfo:
    """Parse a 108 byte beacon (already obfuscated, as received on the wire)."""
    if len(raw) != BEACON_SIZE:
        raise ProtocolError(f"beacon must be {BEACON_SIZE} bytes, got {len(raw)}")
    d = deobfuscate(raw)
    if d[:12] != MAGIC:
        raise ProtocolError("bad magic code")
    sn = d[12:20]
    serial = "%06d%06d" % (int.from_bytes(sn[0:3], "big"), int.from_bytes(sn[3:6], "big"))
    model = d[20:52].split(b"\0", 1)[0].decode("utf-8", "replace").strip()
    ip = f"{d[71]}.{d[70]}.{d[69]}.{d[68]}"
    f84, f85 = d[84], d[85]
    return BoxInfo(
        host=host or ip, serial=serial, model=model, ip=ip,
        platform_id=d[72],
        sw_version=(d[73] << 8) | d[74],
        sw_sub_version=int.from_bytes(d[80:84], "little"),
        customer_id=d[75], model_id=d[76],
        full=bool(f84 & 1),
        data_type=(f84 >> 6) & 1,
        sat_enabled=bool(f84 & 4),
        dlna=bool(f85 & 2), ott=bool(f85 & 4),
        raw=raw,
    )


def handshake_request(device_name: str, client_uuid: str) -> bytes:
    body = (
        "<?xml version='1.0' encoding='UTF-8' standalone='yes' ?>"
        f'<Command request="{REQ_HANDSHAKE}">'
        f"<data>{escape(device_name)}</data><uuid>{escape(client_uuid)}</uuid>"
        "</Command>"
    )
    return frame(body.encode("utf-8"))


def key_request(code: int, data_type: int) -> bytes:
    if data_type == DATA_JSON:
        body = json.dumps(
            {"request": str(REQ_KEY), "array": [{"KeyValue": str(code)}]},
            separators=(",", ":"),
        )
    else:
        body = (
            "<?xml version='1.0' encoding='UTF-8' standalone='yes' ?>"
            f'<Command request="{REQ_KEY}"><KeyValue>{code}</KeyValue></Command>'
        )
    return frame(body.encode("utf-8"))


def request_body(rid: int, data_type: int) -> bytes:
    """A bare query request, e.g. {"request":"15"}."""
    if data_type == DATA_JSON:
        body = json.dumps({"request": str(rid)}, separators=(",", ":"))
    else:
        body = ("<?xml version='1.0' encoding='UTF-8' standalone='yes' ?>"
                f'<Command request="{rid}"/>')
    return frame(body.encode("utf-8"))


REPLY_MAGIC = b"GCDH"


def split_replies(buf: bytes) -> tuple[list[tuple[int, bytes]], bytes]:
    """Split a receive buffer into (request_id, zlib_body) frames.

    Frame: b"GCDH" + u32le body length + u32le request id + u32 0 + body.
    Returns the complete frames and the unconsumed remainder.  Garbage before a
    header is skipped.
    """
    frames: list[tuple[int, bytes]] = []
    while len(buf) >= 16:
        if buf[:4] != REPLY_MAGIC:
            i = buf.find(REPLY_MAGIC, 1)
            buf = buf[i:] if i > 0 else b""
            continue
        length, rid, _ = struct.unpack("<III", buf[4:16])
        if len(buf) < 16 + length:
            break
        frames.append((rid, buf[16:16 + length]))
        buf = buf[16 + length:]
    return frames, buf


def decode_body(body: bytes) -> list | None:
    """zlib + JSON.  Returns None for empty frames (the box's bare acknowledgement)."""
    if not body:
        return None
    try:
        text = zlib.decompressobj().decompress(body)
        data = json.loads(text)
    except (zlib.error, ValueError):
        return None
    return data if isinstance(data, list) else [data]
