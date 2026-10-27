"""Check what state the box is in without wasting client slots.

Usage: python tools/diag.py HOST[:PORT] [press] [--beacon-seconds N]

1. Listens for UDP beacons (this uses no client slot) and prints their "full" flag.
2. Opens ONE session with the stable client UUID and waits for the handshake reply.
3. With "press", sends MENU and then EXIT so you can see the TV react.
"""
import argparse
import asyncio
import time

import _common
from api import Key, discover
from api.const import keymap_for
from api.protocol import BEACON_SIZE, handshake_request, key_request, parse_beacon


async def main(target: str, press: bool, beacon_seconds: float) -> None:
    host, port = _common.parse_target(target)
    print("1) listening for UDP beacons ...")
    boxes = await discover(beacon_seconds)
    for b in boxes:
        print(f"   beacon: {b.host} {b.model} full={b.full} platform={b.platform_id}")
    if not boxes:
        print("   none received (box asleep, still booting, or broadcasts blocked)")

    client = _common.GMScreenClient(host, port)
    print("2) client uuid:", client.client_uuid)
    t0 = time.time()
    try:
        reader, writer = await asyncio.wait_for(asyncio.open_connection(host, port), 5)
    except Exception as err:  # noqa: BLE001
        print("   TCP connect failed:", repr(err))
        return
    print(f"   TCP connected in {time.time() - t0:.2f}s, sending handshake")
    writer.write(handshake_request(client.device_name, client.client_uuid))
    await writer.drain()
    try:
        raw = await asyncio.wait_for(reader.readexactly(BEACON_SIZE), 25)
    except Exception as err:  # noqa: BLE001
        print(f"   no handshake reply after {time.time() - t0:.1f}s: {err!r}")
        writer.close()
        return
    info = parse_beacon(raw, host)
    print(f"   reply after {time.time() - t0:.2f}s  full={info.full}  json={bool(info.data_type)}")
    if press:
        table = keymap_for(info.platform_id)
        for key in (Key.MENU, Key.EXIT):
            print("   sending", key.value)
            writer.write(key_request(table[key], info.data_type))
            await writer.drain()
            await asyncio.sleep(3)
    writer.close()


ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
ap.add_argument("target")
ap.add_argument("press", nargs="?", choices=["press"])
ap.add_argument("--beacon-seconds", type=float, default=8.0)
a = ap.parse_args()
asyncio.run(main(a.target, a.press == "press", a.beacon_seconds))
