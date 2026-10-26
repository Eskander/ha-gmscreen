import asyncio
import json
import unittest

import _api  # noqa: F401
from fake_box import FakeBox
from gmscreen_api import client, const


class ConnectTests(unittest.IsolatedAsyncioTestCase):
    async def test_handshake_returns_box_info(self):
        async with FakeBox(model=b"FUN_60") as box:
            async with client.GMScreenClient("127.0.0.1", box.port, client_uuid="abc") as c:
                self.assertEqual(c.info.model, "FUN_60")
                self.assertTrue(c.connected)
        self.assertIn('<uuid>abc</uuid>', box.handshakes[0])

    async def test_connection_refused_is_a_client_error(self):
        c = client.GMScreenClient("127.0.0.1", 1, timeout=1)
        with self.assertRaises(client.GMScreenError):
            await c.connect()

    async def test_full_box_is_refused(self):
        async with FakeBox(full=True) as box:
            c = client.GMScreenClient("127.0.0.1", box.port)
            with self.assertRaises(client.BoxFullError):
                await c.connect()


class KeyTests(unittest.IsolatedAsyncioTestCase):
    async def test_key_codes_follow_the_platform_table(self):
        for platform_id, expected in ((96, "5"), (30, "27")):
            async with FakeBox(platform_id=platform_id) as box:
                async with client.GMScreenClient("127.0.0.1", box.port) as c:
                    await c.send_key(const.Key.OK)
                    await asyncio.sleep(0.05)
            self.assertEqual(json.loads(box.received[0])["array"][0]["KeyValue"], expected)

    async def test_key_missing_on_platform_is_an_error(self):
        async with FakeBox(platform_id=30) as box:
            async with client.GMScreenClient("127.0.0.1", box.port) as c:
                with self.assertRaises(client.GMScreenError):
                    await c.send_key(const.Key.HOME)      # only the default table has HOME

    async def test_xml_boxes_get_xml_keys(self):
        async with FakeBox(data_type=0) as box:
            async with client.GMScreenClient("127.0.0.1", box.port) as c:
                await c.send_key("menu")
                await asyncio.sleep(0.05)
        self.assertIn('<KeyValue>6</KeyValue>', box.received[0])


class SessionTests(unittest.IsolatedAsyncioTestCase):
    async def test_reconnects_after_the_box_drops_an_idle_session(self):
        async with FakeBox() as box:
            c = client.GMScreenClient("127.0.0.1", box.port)
            await c.send_key(const.Key.OK)
            await asyncio.sleep(0.05)                # let the box read the press first
            box.drop_clients()                       # what the box does after ~25 s idle
            await asyncio.sleep(0.1)
            self.assertFalse(c.connected)
            await c.send_key(const.Key.OK)
            await asyncio.sleep(0.05)
            await c.close()
        self.assertEqual(box.connections, 2)
        self.assertEqual(len(box.received), 2)

    async def test_simultaneous_presses_share_one_session(self):
        async with FakeBox() as box:
            c = client.GMScreenClient("127.0.0.1", box.port)
            await asyncio.gather(*(c.send_key(const.Key.OK) for _ in range(5)))
            await asyncio.sleep(0.05)
            await c.close()
        self.assertEqual(box.connections, 1)
        self.assertEqual(len(box.received), 5)


if __name__ == "__main__":
    unittest.main()
