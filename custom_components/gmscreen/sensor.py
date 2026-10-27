"""Diagnostic sensors.  All are disabled by default; enabling one makes the
integration request the extra data it needs."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from homeassistant.components.sensor import (
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import PERCENTAGE, EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import GMScreenConfigEntry
from .api import BoxStatus
from .entity import GMScreenEntity


@dataclass(frozen=True, kw_only=True)
class GMScreenSensorDescription(SensorEntityDescription):
    value_fn: Callable[[BoxStatus], int | str | None]
    wants: str | None = None          # extra query the coordinator must make


SENSORS = (
    GMScreenSensorDescription(
        key="signal_strength", name="Signal strength", native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT, entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False, icon="mdi:satellite-uplink",
        wants="signal", value_fn=lambda s: s.signal_strength),
    GMScreenSensorDescription(
        key="signal_quality", name="Signal quality", native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT, entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False, icon="mdi:signal",
        wants="signal", value_fn=lambda s: s.signal_quality),
    GMScreenSensorDescription(
        key="channel_count", name="Channel count", entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False, icon="mdi:television-classic",
        value_fn=lambda s: s.channel_count),
)


async def async_setup_entry(
    hass: HomeAssistant, entry: GMScreenConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    async_add_entities(GMScreenSensor(entry, d) for d in SENSORS)


class _WantsMixin:
    """Tell the coordinator which optional queries are needed while enabled."""

    _wants: str | None = None

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()          # type: ignore[misc]
        if self._wants:
            self.coordinator.wanted[self._wants] += 1   # type: ignore[attr-defined]
            await self.coordinator.async_request_refresh()   # type: ignore[attr-defined]

    async def async_will_remove_from_hass(self) -> None:
        if self._wants:
            self.coordinator.wanted[self._wants] -= 1   # type: ignore[attr-defined]
        await super().async_will_remove_from_hass()  # type: ignore[misc]


class GMScreenSensor(_WantsMixin, GMScreenEntity, SensorEntity):
    entity_description: GMScreenSensorDescription

    def __init__(self, entry: GMScreenConfigEntry, description: GMScreenSensorDescription) -> None:
        super().__init__(entry)
        self.entity_description = description
        self._wants = description.wants
        self._attr_unique_id = f"{self._ident}_{description.key}"

    @property
    def native_value(self) -> int | str | None:
        return self.entity_description.value_fn(self.coordinator.data)
