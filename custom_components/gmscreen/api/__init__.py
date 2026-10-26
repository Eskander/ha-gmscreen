"""Client library for set-top boxes controlled by the G-MScreen app."""
from .client import BoxFullError, BoxStatus, GMScreenClient, GMScreenError
from .const import ALL_SATELLITES, DEFAULT_PORT, DISCOVERY_PORT, Key
from .discovery import discover
from .protocol import BoxInfo, ProtocolError, parse_beacon

__all__ = ["ALL_SATELLITES", "BoxFullError", "BoxStatus", "GMScreenClient", "GMScreenError", "Key", "BoxInfo",
           "ProtocolError", "parse_beacon", "discover", "DEFAULT_PORT", "DISCOVERY_PORT"]
