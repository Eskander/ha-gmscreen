import asyncio
import socket
import unittest

import _api  # noqa: F401
from fake_box import make_beacon
from gmscreen_api import discovery


def free_udp_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


class DiscoveryTests(unittest.IsolatedAsyncioTestCase):
    async def test_collects_beacons_and_ignores_noise(self):
        port = free_udp_port()
        task = asyncio.create_task(discovery.discover(timeout=0.5, port=port))
        await asyncio.sleep(0.1)
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.sendto(b"not a beacon", ("127.0.0.1", port))
            s.sendto(bytes(108), ("127.0.0.1", port))                  # right size, bad magic
            s.sendto(make_beacon(model=b"FUN_60"), ("127.0.0.1", port))
            s.sendto(make_beacon(model=b"FUN_60"), ("127.0.0.1", port))  # duplicate
        boxes = await task
        self.assertEqual([b.model for b in boxes], ["FUN_60"])
        self.assertEqual(boxes[0].host, "127.0.0.1")


if __name__ == "__main__":
    unittest.main()
