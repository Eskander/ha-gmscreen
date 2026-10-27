"""Polls the box for power and mute, plus whatever extra readings entities asked for."""
from __future__ import annotations

import logging
from collections import Counter
from datetime import timedelta
from time import monotonic
from typing import TYPE_CHECKING

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import ALL_SATELLITES, BoxStatus, GMScreenClient, GMScreenError
from .const import DOMAIN, SATELLITE_LIST_MAX_AGE, SCAN_INTERVAL_SECONDS

if TYPE_CHECKING:
    from . import GMScreenConfigEntry

_LOGGER = logging.getLogger(__name__)


class GMScreenCoordinator(DataUpdateCoordinator[BoxStatus]):
    config_entry: "GMScreenConfigEntry"

    def __init__(self, hass: HomeAssistant, entry: "GMScreenConfigEntry",
                 client: GMScreenClient) -> None:
        super().__init__(hass, _LOGGER, config_entry=entry, name=DOMAIN,
                         update_interval=timedelta(seconds=SCAN_INTERVAL_SECONDS))
        self.client = client
        # Extra readings are only requested while an enabled entity wants them.
        self.wanted: Counter[str] = Counter()
        self.satellites: dict[int, str] = {}
        self._satellites_at = 0.0

    async def _async_update_data(self) -> BoxStatus:
        try:
            status = await self.client.get_status(
                signal=self.wanted["signal"] > 0, satellite=self.wanted["satellite"] > 0)
        except GMScreenError as err:
            raise UpdateFailed(f"Box not answering: {err}") from err
        idx = status.satellite_index
        if (idx is not None and idx != ALL_SATELLITES and idx not in self.satellites
                and monotonic() - self._satellites_at > SATELLITE_LIST_MAX_AGE):
            self._satellites_at = monotonic()
            try:
                self.satellites = await self.client.get_satellites()
            except GMScreenError as err:
                _LOGGER.debug("Could not read satellite list: %s", err)
        return status
