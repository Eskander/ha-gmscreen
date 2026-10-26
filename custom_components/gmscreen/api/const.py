"""Constants recovered from the G-MScreen Android app (package mktvsmart.screen)."""
from __future__ import annotations

from enum import Enum

DEFAULT_PORT = 20000          # TCP control port on the box
DISCOVERY_PORT = 25860        # UDP port the box broadcasts its beacon to
MAGIC = b"39WwijOog54a"       # first 12 bytes of every (de-obfuscated) beacon
BEACON_SIZE = 108
XOR_KEY = 0x5B

REQ_HANDSHAKE = 998
REQ_KEY = 1040

DATA_XML = 0
DATA_JSON = 1


class Key(str, Enum):
    POWER = "power"
    EXIT = "exit"
    MENU = "menu"
    HOME = "home"
    RED = "red"
    GREEN = "green"
    YELLOW = "yellow"
    BLUE = "blue"
    UP = "up"
    DOWN = "down"
    LEFT = "left"
    RIGHT = "right"
    OK = "ok"
    DIGIT_0 = "0"
    DIGIT_1 = "1"
    DIGIT_2 = "2"
    DIGIT_3 = "3"
    DIGIT_4 = "4"
    DIGIT_5 = "5"
    DIGIT_6 = "6"
    DIGIT_7 = "7"
    DIGIT_8 = "8"
    DIGIT_9 = "9"
    RECALL = "recall"
    TV_RADIO = "tv_radio"
    PAGE_UP = "page_up"
    PAGE_DOWN = "page_down"
    VOLUME_UP = "volume_up"
    VOLUME_DOWN = "volume_down"
    EPG = "epg"
    TXT = "txt"
    SUB = "sub"
    USB = "usb"
    RECORD = "record"
    PLAY = "play"
    STOP = "stop"
    PAUSE = "pause"
    PREVIOUS = "previous"
    NEXT = "next"
    REWIND = "rewind"
    FAST_FORWARD = "fast_forward"


# Key tables copied from GsRemoteControlFragment.  The app picks the table from the
# beacon's platform_id: platform 30 uses its own table, everything else the default.
_D = {
    Key.POWER: 42, Key.EXIT: 7, Key.MENU: 6, Key.HOME: 82,
    Key.RED: 8, Key.GREEN: 9, Key.YELLOW: 10, Key.BLUE: 11,
    Key.UP: 1, Key.DOWN: 2, Key.LEFT: 3, Key.RIGHT: 4, Key.OK: 5,
    Key.DIGIT_0: 12, Key.DIGIT_1: 13, Key.DIGIT_2: 14, Key.DIGIT_3: 15,
    Key.DIGIT_4: 16, Key.DIGIT_5: 17, Key.DIGIT_6: 18, Key.DIGIT_7: 19,
    Key.DIGIT_8: 20, Key.DIGIT_9: 21,
    Key.RECALL: 29, Key.TV_RADIO: 22, Key.PAGE_UP: 37, Key.PAGE_DOWN: 38,
    Key.VOLUME_DOWN: 36, Key.VOLUME_UP: 35, Key.EPG: 32, Key.TXT: 34,
    Key.SUB: 31, Key.USB: 43, Key.RECORD: 58, Key.PLAY: 61, Key.STOP: 62,
    Key.PAUSE: 63, Key.PREVIOUS: 64, Key.NEXT: 65,
    Key.REWIND: 59, Key.FAST_FORWARD: 60,
}

_P30 = {
    Key.POWER: 44, Key.EXIT: 21, Key.MENU: 20,
    Key.RED: 16, Key.GREEN: 17, Key.YELLOW: 18, Key.BLUE: 19,
    Key.LEFT: 22, Key.RIGHT: 23, Key.UP: 24, Key.DOWN: 25, Key.OK: 27,
    Key.DIGIT_0: 10, Key.DIGIT_1: 1, Key.DIGIT_2: 2, Key.DIGIT_3: 3,
    Key.DIGIT_4: 4, Key.DIGIT_5: 5, Key.DIGIT_6: 6, Key.DIGIT_7: 7,
    Key.DIGIT_8: 8, Key.DIGIT_9: 9,
    Key.RECALL: 58, Key.TV_RADIO: 11, Key.PAGE_UP: 34, Key.PAGE_DOWN: 35,
    Key.VOLUME_DOWN: 57, Key.VOLUME_UP: 56, Key.EPG: 29, Key.TXT: 30,
    Key.SUB: 28, Key.USB: 46, Key.RECORD: 43, Key.PLAY: 38, Key.STOP: 39,
    Key.PAUSE: 42, Key.PREVIOUS: 40, Key.NEXT: 41,
    Key.REWIND: 36, Key.FAST_FORWARD: 37,
}

KEYMAPS = {"default": _D, 30: _P30}


def keymap_for(platform_id: int) -> dict[Key, int]:
    return KEYMAPS.get(platform_id, KEYMAPS["default"])
