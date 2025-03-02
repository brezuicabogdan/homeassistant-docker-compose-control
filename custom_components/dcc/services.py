"""DCC Servics."""

import logging

import docker

from homeassistant.core import HomeAssistant, ServiceCall

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


async def async_setup_services(hass: HomeAssistant):
    """Set up services for the dcc component."""

    async def handle_restart(call: ServiceCall):
        """Handle the restart_container service call."""
        entity_id = call.data.get("entity_id")

        # Get entity state from Home Assistant
        entity_state = hass.states.get(entity_id)
        if not entity_state:
            _LOGGER.error("Entity %s has no state", entity_id)
            raise ValueError("Entity " + entity_id + " has no state information.")

        # Retrieve container name and entry_id from entity state
        container_name = entity_state.attributes.get("container_name")
        entry_id = entity_state.attributes.get("entry_id")

        if not container_name:
            _LOGGER.error(
                "Entity %s does not have a container_name attribute", entity_id
            )
            raise ValueError(
                "Entity " + entity_id + " does not have a container_name attribute."
            )

        # Get client from the correct config entry
        client = hass.data[DOMAIN].get(entry_id, {}).get("client")
        if not client:
            _LOGGER.error("Docker client not found for entry %s", entry_id)
            raise ValueError("Docker client not found for this config entry")

        # Run the Docker restart in a separate thread
        await hass.async_add_executor_job(
            restart_docker_container, client, container_name
        )

    # Register the restart_container service
    hass.services.async_register(DOMAIN, "restart_container", handle_restart)


def restart_docker_container(client, container_name):
    """Blocking function to restart a Docker container."""
    try:
        container = client.containers.get(container_name)
        container.restart()
        _LOGGER.info("Container %s restarted successfully", container_name)
    except docker.errors.NotFound as e:
        _LOGGER.error("Container %s not found", container_name)
        raise ValueError("Container " + container_name + " not found.") from e
    except Exception as e:
        _LOGGER.error("Error restarting container %s: %s", container_name, str(e))
        raise ValueError(
            "Error restarting container " + container_name + ": " + str(e)
        ) from e
