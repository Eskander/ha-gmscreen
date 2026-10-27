"""Polls the box for power and mute state."""
from __future__ import annotations

import logging
from datetime import timedelta
from typing import TYPE_CHECKING

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import BoxStatus, GMScreenClient, GMScreenError
from .const import DOMAIN, SCAN_INTERVAL_SECONDS

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

    async def _async_update_data(self) -> BoxStatus:
        try:
            return await self.client.get_status(signal=False, satellite=False)
        except GMScreenError as err:
            raise UpdateFailed(f"Box not answering: {err}") from err
