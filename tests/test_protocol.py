import unittest

import _api  # noqa: F401
from fake_box import make_beacon
from gmscreen_api import const, protocol


class DeobfuscateTests(unittest.TestCase):
    def test_is_its_own_inverse(self):
        for data in (b"", b"a", b"ab", bytes(range(108)), bytes(range(107))):
            self.assertEqual(protocol.deobfuscate(protocol.deobfuscate(data)), data)

    def test_reverses_and_xors(self):
        self.assertEqual(protocol.deobfuscate(b"\x00\x01"), bytes([1 ^ 0x5B, 0 ^ 0x5B]))
        self.assertEqual(protocol.deobfuscate(b"\x00\x01\x02"), bytes([2 ^ 0x5B, 1 ^ 0x5B, 0 ^ 0x5B]))


class FramingTests(unittest.TestCase):
    def test_frame_has_start_length_end(self):
        self.assertEqual(protocol.frame(b"abc"), b"Start0000003Endabc")

    def test_length_is_zero_padded_to_seven_digits(self):
        self.assertEqual(protocol.frame(b"x" * 1234)[:15], b"Start0001234End")


class BeaconTests(unittest.TestCase):
    def test_fields(self):
        info = protocol.parse_beacon(make_beacon(model=b"FUN_60\n", platform_id=96), "10.0.0.5")
        self.assertEqual(info.host, "10.0.0.5")
        self.assertEqual(info.model, "FUN_60")            # trailing newline stripped
        self.assertEqual(info.ip, "192.168.1.100")        # stored in reverse byte order
        self.assertEqual(info.serial, "000258000772")
        self.assertEqual(info.platform_id, 96)
        self.assertEqual(info.sw_version, 391)
        self.assertFalse(info.full)

    def test_data_type_and_full_flag(self):
        self.assertEqual(protocol.parse_beacon(make_beacon(data_type=1)).data_type, const.DATA_JSON)
        self.assertEqual(protocol.parse_beacon(make_beacon(data_type=0)).data_type, const.DATA_XML)
        self.assertTrue(protocol.parse_beacon(make_beacon(full=True)).full)

    def test_rejects_wrong_size_and_magic(self):
        with self.assertRaises(protocol.ProtocolError):
            protocol.parse_beacon(b"short")
        with self.assertRaises(protocol.ProtocolError):
            protocol.parse_beacon(bytes(const.BEACON_SIZE))


class RequestTests(unittest.TestCase):
    def test_handshake_is_xml_with_uuid(self):
        body = protocol.handshake_request("Home <Assistant>", "abc-123")
        self.assertTrue(body.startswith(b"Start"))
        self.assertIn(b'<Command request="998">', body)
        self.assertIn(b"<data>Home &lt;Assistant&gt;</data>", body)
        self.assertIn(b"<uuid>abc-123</uuid>", body)

    def test_key_request_json_and_xml(self):
        self.assertTrue(protocol.key_request(5, const.DATA_JSON).endswith(
            b'{"request":"1040","array":[{"KeyValue":"5"}]}'))
        self.assertTrue(protocol.key_request(5, const.DATA_XML).endswith(
            b'<Command request="1040"><KeyValue>5</KeyValue></Command>'))


class KeyTableTests(unittest.TestCase):
    def test_default_and_platform_30_differ(self):
        self.assertEqual(const.keymap_for(96)[const.Key.OK], 5)
        self.assertEqual(const.keymap_for(30)[const.Key.OK], 27)

    def test_mute_codes(self):
        self.assertEqual(const.keymap_for(96)[const.Key.MUTE], 23)
        self.assertEqual(const.keymap_for(30)[const.Key.MUTE], 12)

    def test_every_key_has_a_default_code(self):
        self.assertEqual(set(const.keymap_for(96)), set(const.Key))


if __name__ == "__main__":
    unittest.main()
