"""Remote entity: send key presses to the box."""
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
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import GMScreenConfigEntry
from .api import GMScreenError, Key
from .const import DOMAIN


async def async_setup_entry(
    hass: HomeAssistant, entry: GMScreenConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    async_add_entities([GMScreenRemote(entry)])


class GMScreenRemote(RemoteEntity):
    """The box reports no state yet, so this entity is always 'on' (it means: usable).

    Commands are key names (menu, ok, up, volume_up, 5, ...) or 'code:NN' for a raw
    key code. Power is a toggle on these boxes: send the 'power' command.
    """

    _attr_has_entity_name = True
    _attr_name = None
    _attr_should_poll = False
    _attr_is_on = True

    def __init__(self, entry: GMScreenConfigEntry) -> None:
        self._client = entry.runtime_data
        ident = entry.unique_id or entry.entry_id
        self._attr_unique_id = ident
        info = self._client.info
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, ident)},
            name=entry.title,
            model=info.model if info else None,
        )

    async def async_send_command(self, command: Iterable[str], **kwargs: Any) -> None:
        repeats = kwargs.get(ATTR_NUM_REPEATS, 1)
        delay = kwargs.get(ATTR_DELAY_SECS, DEFAULT_DELAY_SECS)
        commands = [c for _ in range(repeats) for c in command]
        for i, cmd in enumerate(commands):
            if i:
                await asyncio.sleep(delay)
            await self._send(cmd)

    async def _send(self, cmd: str) -> None:
        cmd = cmd.strip().lower()
        try:
            if cmd.startswith("code:"):
                await self._client.send_code(int(cmd[5:]))
            else:
                await self._client.send_key(Key(cmd))
        except ValueError as err:
            raise ServiceValidationError(
                f"Unknown command '{cmd}'. Use a key name such as menu, ok, up, volume_up, "
                "or code:NN for a raw key code."
            ) from err
        except GMScreenError as err:
            raise HomeAssistantError(f"Could not send '{cmd}': {err}") from err
