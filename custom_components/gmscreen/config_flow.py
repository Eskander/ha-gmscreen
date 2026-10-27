"""Config flow: find the box by its UDP beacon or enter its IP manually."""
from __future__ import annotations

import uuid
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_HOST, CONF_PORT

from .api import DEFAULT_PORT, BoxFullError, GMScreenClient, GMScreenError, discover
from .const import CONF_CLIENT_UUID, DOMAIN


class GMScreenConfigFlow(ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        default_host = ""

        if user_input is not None:
            host = user_input[CONF_HOST].strip()
            default_host = host
            client_uuid = str(uuid.uuid4())  # one identity per entry, reused forever
            client = GMScreenClient(host, DEFAULT_PORT, client_uuid=client_uuid,
                                    device_name="HomeAssistant")
            try:
                info = await client.connect(full_retries=1, full_delay=2.0)
            except BoxFullError:
                errors["base"] = "box_full"
            except GMScreenError:
                errors["base"] = "cannot_connect"
            else:
                await self.async_set_unique_id(info.serial)
                self._abort_if_unique_id_configured(updates={CONF_HOST: host})
                return self.async_create_entry(
                    title=info.model or "G-MScreen box",
                    data={CONF_HOST: host, CONF_PORT: DEFAULT_PORT, CONF_CLIENT_UUID: client_uuid},
                )
            finally:
                await client.close()
        else:
            boxes = await discover(5)
            if boxes:
                default_host = boxes[0].host

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({vol.Required(CONF_HOST, default=default_host): str}),
            errors=errors,
        )
