"""Poll the state queries the box answers and print every change.

Usage: python tools/watch.py HOST[:PORT] [seconds]

Press buttons on the physical remote (mute, volume, standby, channel change)
and see which replies move. Constant polling also shows whether the box still
drops the session after ~25 s.
"""
import asyncio
import json
import sys
import time

import _common
from api.protocol import frame

QUERIES = [15, 19, 23]


async def main(target: str, total: float) -> None:
    t0 = time.time()
    last: dict[int, str] = {}
    c = await _common.open_session(target)
    session_start = time.time()
    print(f"[{0:6.1f}] connected; polling {QUERIES} for {total:.0f} s")
    while time.time() - t0 < total:
        for rid in QUERIES:
            c._writer.write(frame(json.dumps({"request": str(rid)}, separators=(",", ":")).encode()))
            await c._writer.drain()
            data, closed = await _common.collect(c._reader, quiet=0.4, maximum=1.5)
            frames, _ = _common.describe(data)
            text = " | ".join(t for r, t in frames if r == rid and t != "<empty>") or "<no reply>"
            if last.get(rid) != text:
                print(f"[{time.time() - t0:6.1f}] {rid}: {text[:300]}")
                last[rid] = text
            if closed:
                print(f"[{time.time() - t0:6.1f}] box closed the session after "
                      f"{time.time() - session_start:.0f} s; reconnecting")
                await c.close()
                c = await _common.open_session(target)
                session_start = time.time()
                break
        await asyncio.sleep(1.5)
    await c.close()


if len(sys.argv) < 2:
    sys.exit(__doc__)
asyncio.run(main(sys.argv[1], float(sys.argv[2]) if len(sys.argv) > 2 else 120))
