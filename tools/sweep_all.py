"""Send every plausible bare request id to the box and log the replies.

Usage: python tools/sweep_all.py HOST[:PORT] [--resume] [--delay 0.5] [--ids 15,19]

Each request is {"request":"N"} with no payload. The ids are the ones the app
uses plus their neighbours. Ids that look like settings, updates or edits go
LAST so the harmless data is collected first. The script checks that the box
still answers request 15 every 20 requests and stops if it does not.

WARNING: even bare requests can make a box do things (reboot, clear data).
Only run this against a box you can factory reset.

Watch the TV while it runs: the line printed just before something odd
happens on screen is the id responsible. Replies can arrive late, so the log
stores each reply with the id from its header.

Output: sweep_all.jsonl (one JSON object per id, raw hex of real replies).
"""
import argparse
import asyncio
import json
import os
import re

import _common
from api import GMScreenError
from api.protocol import frame

LOG = "sweep_all.jsonl"
SKIP = {998, 1040}                     # handshake and key press, already understood
LAST = {9, 13, 25, 29, 1004, 1010, 1041, 1043, 1050, 1051, 1052, 1053, 1054, 1055,
        1058, 1059, 1060}              # parental lock, update, debug, editing
EMPTY = '[{"Command":""}]'            # what the box says to ids it does not implement


def id_order() -> list[int]:
    base = [*range(0, 121), *range(300, 311), *range(400, 411), *range(1000, 1111),
            *range(1300, 1311), *range(2000, 2031), 4100]
    base = [i for i in base if i not in SKIP]
    return [i for i in base if i not in LAST] + sorted(LAST & set(base))


async def ask(c, rid: int, quiet: float):
    c._writer.write(frame(json.dumps({"request": str(rid)}, separators=(",", ":")).encode()))
    await c._writer.drain()
    data, closed = await _common.collect(c._reader, quiet, maximum=3.0)
    frames, _ = _common.describe(data)
    return data, frames, closed


def classify(rid: int, data: bytes, frames: list[tuple[int, str]], closed: bool) -> str:
    if closed:
        return "closed session"
    if not data:
        return "no reply"
    texts = [re.sub(r"\s+", "", t) for _, t in frames]
    if frames and all(r == rid for r, _ in frames) and all(t in ("<empty>", EMPTY) for t in texts):
        return "empty" if EMPTY in texts else "ack only"
    return "** " + " | ".join(f"[{r}] {t}" for r, t in frames)[:150]


async def healthy(c) -> bool:
    try:
        _, frames, closed = await ask(c, 15, 0.6)
    except OSError:
        return False
    return not closed and any("StbStatus" in text for _, text in frames)


async def main(target: str, resume: bool, delay: float, only: list[int] | None) -> None:
    done: set[int] = set()
    if resume and os.path.exists(LOG):
        done = {json.loads(line)["id"] for line in open(LOG) if line.strip()}
    todo = [i for i in (only or id_order()) if i not in done]
    print(f"{len(todo)} ids to try")
    c = await _common.open_session(target)
    log = open(LOG, "a")
    for n, rid in enumerate(todo):
        if n and n % 20 == 0 and not await healthy(c):
            print("box did not answer the health check; waiting 5 s and retrying once")
            await asyncio.sleep(5)
            try:
                await c.close()
                c = await _common.open_session(target)
            except GMScreenError:
                print(f"STOP: box unreachable after id {todo[n - 1]}")
                break
            if not await healthy(c):
                print(f"STOP: box no longer answers queries after id {todo[n - 1]}")
                break
        try:
            data, frames, closed = await ask(c, rid, delay)
        except OSError:
            data, frames, closed = b"", [], True
        tag = classify(rid, data, frames, closed)
        print(f"{rid:5}  {tag}", flush=True)
        log.write(json.dumps({"id": rid, "tag": tag, "hex": data.hex() if tag.startswith("**") else ""}) + "\n")
        log.flush()
        if closed:
            await asyncio.sleep(2)
            try:
                await c.close()
                c = await _common.open_session(target)
            except GMScreenError as err:
                print(f"STOP: could not reconnect: {err}")
                break
    await c.close()
    print("done; full log in", LOG)


ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
ap.add_argument("target")
ap.add_argument("--resume", action="store_true")
ap.add_argument("--delay", type=float, default=0.5)
ap.add_argument("--ids", help="comma separated ids instead of the full list")
a = ap.parse_args()
asyncio.run(main(a.target, a.resume, a.delay, [int(x) for x in a.ids.split(",")] if a.ids else None))
