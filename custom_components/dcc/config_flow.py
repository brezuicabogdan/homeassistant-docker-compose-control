"""Config flow for HA Docker Compose Control integration."""

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import callback
import homeassistant.helpers.config_validation as cv

from .const import DEFAULT_CONTAINER_IMAGE_UPDATE_INTERVAL, DOMAIN
from .validators import validate_compose_file, validate_docker_socket


class HaDccConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """HA Docker Compose Control config flow."""

    async def async_step_user(self, user_input=None):
        """Handle a flow initiated by the user."""
        errors = {}

        if user_input is not None:
            docker_socket = user_input["docker_socket"]
            compose_file = user_input["compose_file"]
            container_image_update_check_interval = user_input.get(
                "container_image_update_check_interval",
                DEFAULT_CONTAINER_IMAGE_UPDATE_INTERVAL,
            )

            if (
                not isinstance(container_image_update_check_interval, int)
                or container_image_update_check_interval <= 0
            ):
                errors["container_image_update_check_interval"] = (
                    "The container image update check interval must be a positive number."
                )

            existing_entry = self._check_existing_entry(docker_socket, compose_file)
            if existing_entry:
                return self.async_abort(
                    reason="The same docker socket and docker-compose file are already configured"
                )

            try:
                await validate_docker_socket(docker_socket)
            except vol.Invalid as e:
                errors["docker_socket"] = str(e)

            try:
                await validate_compose_file(compose_file)
            except vol.Invalid as e:
                errors["compose_file"] = str(e)

            if not errors:
                return self.async_create_entry(
                    title="HA Docker Compose Control",
                    data={
                        "docker_socket": docker_socket,
                        "compose_file": compose_file,
                        "container_image_update_check_interval": container_image_update_check_interval,
                    },
                )

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        "docker_socket", default="/var/run/docker.sock"
                    ): cv.string,
                    vol.Required(
                        "compose_file", default="/containers/docker-compose.yaml"
                    ): cv.string,
                    vol.Optional(
                        "container_image_update_check_interval",
                        default=DEFAULT_CONTAINER_IMAGE_UPDATE_INTERVAL,
                    ): vol.All(vol.Coerce(int), vol.Range(min=1)),
                }
            ),
            errors=errors,
        )

    @callback
    def _check_existing_entry(self, docker_socket, compose_file):
        """Check if a config entry with the same Docker socket + Compose file exists."""
        for entry in self._async_current_entries():
            if (
                entry.data["docker_socket"] == docker_socket
                and entry.data["compose_file"] == compose_file
            ):
                return entry
        return None
