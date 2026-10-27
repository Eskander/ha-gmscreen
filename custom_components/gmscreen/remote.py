"""Remote entity: power state plus key presses."""
from __future__ import annotations

import asyncio
from collections.abc import Iterable
from typing import Any

from homeassistant.components.remote import (
    ATTR_DELAY_SECS,
    ATTR_NUM_REPEATS,
    DEFAULT_DELAY_SECS,
    RemoteEntity,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import GMScreenConfigEntry
from .entity import GMScreenEntity


async def async_setup_entry(
    hass: HomeAssistant, entry: GMScreenConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    async_add_entities([GMScreenRemote(entry)])


class GMScreenRemote(GMScreenEntity, RemoteEntity):
    """On means the box is running, off means standby.

    Power is a toggle key on these boxes, so turn_on / turn_off only press it when the
    reported state differs.  Commands are key names (menu, ok, up, volume_up, mute, 5,
    ...) or 'code:NN' for a raw key code.
    """

    _attr_name = None

    def __init__(self, entry: GMScreenConfigEntry) -> None:
        super().__init__(entry)
        self._attr_unique_id = self._ident

    @property
    def is_on(self) -> bool | None:
        return self.coordinator.data.power

    async def async_turn_on(self, **kwargs: Any) -> None:
        if self.is_on is not True:
            await self._press("power")
            await self._refresh_soon()

    async def async_turn_off(self, **kwargs: Any) -> None:
        if self.is_on is not False:
            await self._press("power")
            await self._refresh_soon()

    async def async_send_command(self, command: Iterable[str], **kwargs: Any) -> None:
        repeats = kwargs.get(ATTR_NUM_REPEATS, 1)
        delay = kwargs.get(ATTR_DELAY_SECS, DEFAULT_DELAY_SECS)
        commands = [c for _ in range(repeats) for c in command]
        for i, cmd in enumerate(commands):
            if i:
                await asyncio.sleep(delay)
            await self._press(cmd)
        if any(c.strip().lower() in ("power", "mute") for c in commands):
            await self._refresh_soon()
