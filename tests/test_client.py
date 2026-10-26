import asyncio
import json
import unittest

import _api  # noqa: F401
from fake_box import FakeBox, gcdh
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
                await c.connect(full_retries=0)


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

    async def test_full_box_is_retried_before_giving_up(self):
        async with FakeBox(full=True) as box:
            c = client.GMScreenClient("127.0.0.1", box.port)
            with self.assertRaises(client.BoxFullError):
                await c.connect(full_retries=2, full_delay=0.01)
        self.assertEqual(box.connections, 3)

    async def test_allow_full_proceeds_anyway(self):
        async with FakeBox(full=True) as box:
            c = client.GMScreenClient("127.0.0.1", box.port)
            info = await c.connect(allow_full=True)
            self.assertTrue(info.full)
            await c.close()


class IdentityTests(unittest.TestCase):
    def test_default_uuid_is_stable_per_host_and_name(self):
        a = client.GMScreenClient("192.168.1.5").client_uuid
        self.assertEqual(a, client.GMScreenClient("192.168.1.5").client_uuid)
        self.assertNotEqual(a, client.GMScreenClient("192.168.1.6").client_uuid)
        self.assertNotEqual(a, client.GMScreenClient("192.168.1.5", device_name="x").client_uuid)

    def test_explicit_uuid_wins(self):
        self.assertEqual(client.GMScreenClient("h", client_uuid="fixed").client_uuid, "fixed")


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


class QueryTests(unittest.IsolatedAsyncioTestCase):
    async def test_reply_is_matched_by_its_header_id(self):
        # a stale frame for another request, a bare acknowledgement, then the answer
        replies = {15: gcdh(999, [{"stale": 1}]) + gcdh(15, None) + gcdh(15, [{"StbStatus": 1}])}
        async with FakeBox(replies=replies) as box:
            c = client.GMScreenClient("127.0.0.1", box.port)
            self.assertEqual(await c.request(15), [{"StbStatus": 1}])
            await c.close()

    async def test_concurrent_queries_each_get_their_own_answer(self):
        replies = {15: gcdh(15, [{"StbStatus": 0}]), 19: gcdh(19, [{"Data": "1"}])}
        async with FakeBox(replies=replies) as box:
            c = client.GMScreenClient("127.0.0.1", box.port)
            a, b = await asyncio.gather(c.request(19), c.request(15))
            await c.close()
        self.assertEqual((a, b), ([{"Data": "1"}], [{"StbStatus": 0}]))
        self.assertEqual(box.connections, 1)

    async def test_unanswered_query_raises_and_resets_the_session(self):
        async with FakeBox() as box:              # answers nothing
            c = client.GMScreenClient("127.0.0.1", box.port)
            with self.assertRaises(client.GMScreenError):
                await c.request(15, timeout=0.2)
            self.assertFalse(c.connected)
        self.assertEqual(box.connections, 2)       # one retry on a fresh session

    async def test_late_reply_for_an_earlier_request_is_ignored(self):
        replies = {19: gcdh(15, [{"late": 1}]) + gcdh(19, [{"Data": "0"}])}
        async with FakeBox(replies=replies) as box:
            c = client.GMScreenClient("127.0.0.1", box.port)
            self.assertEqual(await c.request(19), [{"Data": "0"}])
            await c.close()


STB_ON = [{"StbStatus": 1, "ProductName": "FUN_60", "SoftwareVersion": "3.87",
           "SerialNumber": "210502018517", "ChannelNum": 1256}]


class StatusTests(unittest.IsolatedAsyncioTestCase):
    async def test_box_on(self):
        replies = {15: gcdh(15, STB_ON), 19: gcdh(19, [{"Data": "0"}]),
                   403: gcdh(403, [{"strength": 96, "quality": 90}]),
                   23: gcdh(23, [{"Data": "120"}])}
        async with FakeBox(replies=replies) as box:
            c = client.GMScreenClient("127.0.0.1", box.port)
            st = await c.get_status()
            await c.close()
        self.assertEqual(st.satellite_index, const.ALL_SATELLITES)
        self.assertIs(st.power, True)
        self.assertIs(st.muted, False)
        self.assertEqual((st.signal_strength, st.signal_quality), (96, 90))
        self.assertEqual((st.channel_count, st.software_version, st.product, st.serial),
                         (1256, "3.87", "FUN_60", "210502018517"))

    async def test_standby_and_muted_skip_the_signal_query(self):
        replies = {15: gcdh(15, [{"StbStatus": 0}]), 19: gcdh(19, [{"Data": "1"}])}
        async with FakeBox(replies=replies) as box:
            c = client.GMScreenClient("127.0.0.1", box.port)
            st = await c.get_status()
            await c.close()
        self.assertIs(st.power, False)
        self.assertIs(st.muted, True)
        self.assertIsNone(st.signal_strength)
        self.assertEqual(len(box.received), 2)      # 15 and 19 only, never 403

    async def test_missing_fields_become_none(self):
        replies = {15: gcdh(15, [{"Command": ""}]), 19: gcdh(19, [{"Command": ""}])}
        async with FakeBox(replies=replies) as box:
            c = client.GMScreenClient("127.0.0.1", box.port)
            st = await c.get_status()
            await c.close()
        self.assertIsNone(st.power)
        self.assertIsNone(st.muted)

    async def test_unanswered_signal_query_does_not_fail_the_status(self):
        replies = {15: gcdh(15, STB_ON), 19: gcdh(19, [{"Data": "0"}])}   # no 403 reply
        async with FakeBox(replies=replies) as box:
            c = client.GMScreenClient("127.0.0.1", box.port)
            st = await c.get_status(timeout=0.2)
            await c.close()
        self.assertIs(st.power, True)
        self.assertIsNone(st.signal_strength)


SATELLITES = [{"SatName": "Hotbird ", "SatIndex": 1, "SatAngle": 130, "SatDir": 0},
              {"SatName": "Nilesat", "SatIndex": 84, "SatAngle": 70, "SatDir": 1}]


class SatelliteTests(unittest.IsolatedAsyncioTestCase):
    async def test_selected_satellite_is_read_when_requested(self):
        replies = {15: gcdh(15, STB_ON), 19: gcdh(19, [{"Data": "0"}]),
                   23: gcdh(23, [{"Data": "84"}])}
        async with FakeBox(replies=replies) as box:
            c = client.GMScreenClient("127.0.0.1", box.port)
            st = await c.get_status(signal=False)
            await c.close()
        self.assertEqual(st.satellite_index, 84)
        self.assertIsNone(st.signal_strength)

    async def test_optional_queries_are_not_sent_unless_asked_for(self):
        replies = {15: gcdh(15, STB_ON), 19: gcdh(19, [{"Data": "0"}])}
        async with FakeBox(replies=replies) as box:
            c = client.GMScreenClient("127.0.0.1", box.port)
            await c.get_status(signal=False, satellite=False)
            await c.close()
        self.assertEqual(len(box.received), 2)

    async def test_satellite_list_maps_index_to_trimmed_name(self):
        async with FakeBox(replies={22: gcdh(22, SATELLITES)}) as box:
            c = client.GMScreenClient("127.0.0.1", box.port)
            self.assertEqual(await c.get_satellites(), {1: "Hotbird", 84: "Nilesat"})
            await c.close()

    def test_120_means_all_satellites(self):
        self.assertEqual(const.ALL_SATELLITES, 120)


if __name__ == "__main__":
    unittest.main()
