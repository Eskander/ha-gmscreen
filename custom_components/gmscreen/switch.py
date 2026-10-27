"""Mute as a switch: shows the real mute state and toggles it."""
from __future__ import annotations

from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import GMScreenConfigEntry
from .entity import GMScreenEntity


async def async_setup_entry(
    hass: HomeAssistant, entry: GMScreenConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    async_add_entities([GMScreenMute(entry)])


class GMScreenMute(GMScreenEntity, SwitchEntity):
    """The box only has a mute toggle key, so this presses it when the state differs."""

    _attr_name = "Mute"

    def __init__(self, entry: GMScreenConfigEntry) -> None:
        super().__init__(entry)
        self._attr_unique_id = f"{self._ident}_mute"

    @property
    def is_on(self) -> bool | None:
        return self.coordinator.data.muted

    @property
    def icon(self) -> str:
        return "mdi:volume-off" if self.is_on else "mdi:volume-high"

    async def async_turn_on(self, **kwargs: Any) -> None:
        if self.is_on is not True:
            await self._press("mute")
            await self._refresh_soon(1.5)

    async def async_turn_off(self, **kwargs: Any) -> None:
        if self.is_on is not False:
            await self._press("mute")
            await self._refresh_soon(1.5)
