"""Shared entity base."""
from __future__ import annotations

import asyncio

from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import GMScreenConfigEntry
from .api import GMScreenError, Key
from .const import DOMAIN
from .coordinator import GMScreenCoordinator


class GMScreenEntity(CoordinatorEntity[GMScreenCoordinator]):
    _attr_has_entity_name = True

    def __init__(self, entry: GMScreenConfigEntry) -> None:
        super().__init__(entry.runtime_data.coordinator)
        self._client = entry.runtime_data.client
        self._ident = entry.unique_id or entry.entry_id
        info = self._client.info
        status = self.coordinator.data
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, self._ident)},
            name=entry.title,
            model=(info.model if info else None) or status.product,
            sw_version=status.software_version,
            serial_number=status.serial or (info.serial if info else None),
        )

    async def _press(self, cmd: str) -> None:
        """Send a key by name, or 'code:NN' for a raw code."""
        cmd = cmd.strip().lower()
        try:
            if cmd.startswith("code:"):
                await self._client.send_code(int(cmd[5:]))
            else:
                await self._client.send_key(Key(cmd))
        except ValueError as err:
            raise ServiceValidationError(
                f"Unknown command '{cmd}'. Use a key name such as menu, ok, up, volume_up, "
                "mute, or code:NN for a raw key code."
            ) from err
        except GMScreenError as err:
            raise HomeAssistantError(f"Could not send '{cmd}': {err}") from err

    async def _refresh_soon(self, delay: float = 2.0) -> None:
        await asyncio.sleep(delay)
        await self.coordinator.async_request_refresh()
