"""G-MScreen set-top box integration."""
from __future__ import annotations

from dataclasses import dataclass

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PORT, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady

from .api import DEFAULT_PORT, GMScreenClient, GMScreenError
from .const import CONF_CLIENT_UUID
from .coordinator import GMScreenCoordinator

PLATFORMS = [Platform.REMOTE]


@dataclass
class GMScreenData:
    client: GMScreenClient
    coordinator: GMScreenCoordinator


type GMScreenConfigEntry = ConfigEntry[GMScreenData]


async def async_setup_entry(hass: HomeAssistant, entry: GMScreenConfigEntry) -> bool:
    client = GMScreenClient(
        entry.data[CONF_HOST],
        entry.data.get(CONF_PORT, DEFAULT_PORT),
        client_uuid=entry.data[CONF_CLIENT_UUID],
        device_name="HomeAssistant",
    )
    try:
        await client.connect()
    except GMScreenError as err:
        raise ConfigEntryNotReady(f"Cannot reach box at {entry.data[CONF_HOST]}: {err}") from err

    coordinator = GMScreenCoordinator(hass, entry, client)
    try:
        await coordinator.async_config_entry_first_refresh()
    except Exception:
        await client.close()
        raise
    entry.runtime_data = GMScreenData(client, coordinator)
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: GMScreenConfigEntry) -> bool:
    if unloaded := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        await entry.runtime_data.client.close()
    return unloaded
