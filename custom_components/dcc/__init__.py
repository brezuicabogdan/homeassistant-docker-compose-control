"""Homeassistant Docker Compose Component."""

from datetime import timedelta
import json
import logging

import aiofiles
import docker
import voluptuous as vol
import yaml

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
import homeassistant.helpers.config_validation as cv
import homeassistant.helpers.device_registry as dr
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .validators import validate_compose_file, validate_docker_socket

_LOGGER = logging.getLogger(__name__)

DOMAIN = "dcc"

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)


async def async_setup(hass: HomeAssistant, config: dict):
    """Set up the Docker Compose Component."""
    hass.data.setdefault(DOMAIN, {})
    return True


async def async_setup_entry(hass: HomeAssistant, entry):
    """Component setup for the integration."""
    docker_socket = entry.data.get("docker_socket")
    compose_file = entry.data.get("compose_file")

    hass.config_entries.async_update_entry(
        entry, title=f"{compose_file} on {docker_socket}"
    )

    # Validate Docker socket
    try:
        await validate_docker_socket(docker_socket)
    except vol.Invalid as e:
        _LOGGER.error("Docker socket validation failed: %s", e)
        return False

    # Offload Docker client initialization to avoid blocking the event loop
    def get_docker_client():
        return docker.DockerClient(base_url=f"unix://{docker_socket}")

    try:
        client = await hass.async_add_executor_job(get_docker_client)
        hass.data["ha_dcc"] = {"client": client}
    except docker.errors.DockerException as e:
        _LOGGER.error("Failed to connect to Docker: %s", e)
        return False
    except PermissionError:
        _LOGGER.error(
            "Permission denied while accessing Docker. Ensure propper permissions to {docker_socket}"
        )
        return False
    except Exception as e:  # noqa: BLE001
        _LOGGER.error("Unexpected error: %s", e)
        return False

    # Validate Docker Compose file
    try:
        await validate_compose_file(compose_file)
    except vol.Invalid as e:
        _LOGGER.error("Docker Compose file validation failed: %s", e)
        return False

    async with aiofiles.open(compose_file) as file:
        content = await file.read()
        compose_data = yaml.safe_load(content)

    services = {
        service_data.get("container_name", service_name): service_name
        for service_name, service_data in compose_data.get("services", {}).items()
    }

    # Store client & services in HA data
    hass.data[DOMAIN][entry.entry_id] = {
        "client": client,
        "docker_socket": docker_socket,
        "compose_file": compose_file,
        "services": services,
    }

    # Register the device
    device_registry = dr.async_get(hass)
    device = device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, entry.entry_id)},
        manufacturer="HA DCC",
        model="Docker Compose",
        name=f"{compose_file} on {docker_socket}",
    )
    hass.config_entries.async_update_entry(entry, title=device.name)

    # Create an update coordinator to manage updates
    coordinator = DataUpdateCoordinator(
        hass,
        _LOGGER,
        name=f"DCC {entry.entry_id}",
        update_method=lambda: update_docker_status(hass, client, services),
        update_interval=timedelta(seconds=30),  # Adjust update frequency as needed
    )

    # Store coordinator
    hass.data[DOMAIN][entry.entry_id]["coordinator"] = coordinator

    # Forward entry setup to the sensor platform
    await hass.config_entries.async_forward_entry_setups(entry, ["sensor"])

    return True


async def update_docker_status(hass: HomeAssistant, client, services):
    """Fetch updated Docker container status."""
    status = {}

    def get_container_status(service_name):
        """Fetch container status by service name, ignoring container_name overrides."""
        try:
            # Get all containers (running and stopped)
            containers = client.containers.list(all=True)

            # Try matching by `com.docker.compose.service`
            for container in containers:
                labels = container.labels  # Get container labels safely
                if labels.get("com.docker.compose.service") == service_name:
                    _LOGGER.debug(
                        "Found container by label: %s",
                        json.dumps(container.attrs, indent=4),
                    )
                    container_info = container.attrs
                    return {
                        "status": container.status,  # Running, Exited, etc.
                        "health": container_info.get("State", {})
                        .get("Health", {})
                        .get("Status", "unknown"),
                        "restart_count": container_info.get("RestartCount", 0),
                        "image": container_info.get("Config", {}).get(
                            "Image", "unknown"
                        ),
                        "uptime": container_info.get("State", {}).get(
                            "StartedAt", "unknown"
                        ),
                    }

            # Fallback: Check by container name
            for container in containers:
                if container.name == service_name:  # Direct name check
                    _LOGGER.debug(
                        "Found container by name: %s",
                        json.dumps(container.attrs, indent=4),
                    )
                    container_info = container.attrs
                    return {
                        "status": container.status,  # Running, Exited, etc.
                        "health": container_info.get("State", {})
                        .get("Health", {})
                        .get("Status", "unknown"),
                        "restart_count": container_info.get("RestartCount", 0),
                        "image": container_info.get("Config", {}).get(
                            "Image", "unknown"
                        ),
                        "uptime": container_info.get("State", {}).get(
                            "StartedAt", "unknown"
                        ),
                    }

        except Exception as e:  # noqa: BLE001
            _LOGGER.error("Error fetching container status for %s: %s", service_name, e)
            return "unknown"
        else:
            return "not_found"  # If not found by either method

    # Run each container lookup in a separate thread
    for service in services:
        status[service] = await hass.async_add_executor_job(
            get_container_status, service
        )

    return status


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Unload a config entry."""
    await hass.config_entries.async_forward_entry_unload(entry, "sensor")
    hass.data[DOMAIN].pop(entry.entry_id)
    return True
