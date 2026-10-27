"""Send bare queries (or full JSON bodies) and print the decoded replies.

Usage: python tools/request.py HOST[:PORT] ARG [ARG ...]

ARG is a request number (sends {"request":"N"}) or a complete JSON body, e.g.
  python tools/request.py 192.168.1.187 15 19 22
  python tools/request.py 192.168.1.187 '{"request":"0","FromIndex":"0","ToIndex":"20"}'

One session is used for all requests; the box drops idle sessions after ~25 s.
Raw replies are saved to reply_<n>_<arg>.bin in the current directory.
"""
import asyncio
import json
import re
import sys

import _common
from api.protocol import frame


async def main(target: str, args: list[str]) -> None:
    c = await _common.open_session(target)
    print(f"connected: {c.info.model}, json={bool(c.info.data_type)}")
    for n, arg in enumerate(args):
        body = arg if arg.lstrip().startswith("{") else json.dumps({"request": arg}, separators=(",", ":"))
        print(f"\n>> {body}")
        c._writer.write(frame(body.encode()))
        await c._writer.drain()
        data, closed = await _common.collect(c._reader, quiet=1.5, maximum=8.0)
        name = re.sub(r"[^A-Za-z0-9]+", "_", arg)[:16]
        with open(f"reply_{n}_{name}.bin", "wb") as fh:
            fh.write(data)
        frames, rest = _common.describe(data)
        if not frames:
            print(f"   {len(data)} raw bytes: {data[:96].hex(' ')}")
        for rid, text in frames:
            print(f"<< id {rid}: {text[:1500]}")
        if rest:
            print(f"   {len(rest)} unparsed trailing bytes")
        if closed:
            print("   (box closed the session)")
            break
    await c.close()


if len(sys.argv) < 3:
    sys.exit(__doc__)
asyncio.run(main(sys.argv[1], sys.argv[2:]))
