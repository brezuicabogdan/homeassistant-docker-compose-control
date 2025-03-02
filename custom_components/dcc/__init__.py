"""Homeassistant Docker Compose Component."""

from datetime import timedelta
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

from .const import DOMAIN
from .services import async_setup_services
from .validators import validate_compose_file, validate_docker_socket

_LOGGER = logging.getLogger(__name__)

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)


async def async_setup(hass: HomeAssistant, config: dict):
    """Set up the Docker Compose Component."""
    hass.data.setdefault(DOMAIN, {})
    await async_setup_services(hass)
    return True


async def async_setup_entry(hass: HomeAssistant, entry):
    """Component setup for the integration."""
    docker_socket = entry.data.get("docker_socket")
    compose_file = entry.data.get("compose_file")

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
        hass.data[DOMAIN] = {"client": client}
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

    hass.config_entries.async_update_entry(
        entry, title=f"{compose_file} on {docker_socket}"
    )

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

    coordinator = DataUpdateCoordinator(
        hass,
        _LOGGER,
        name=f"DCC {entry.entry_id}",
        update_method=lambda: update_docker_status(
            hass, client, services, entry.entry_id
        ),
        update_interval=timedelta(seconds=30),  # Adjust update frequency
    )

    # Store coordinator for sensor access
    hass.data[DOMAIN][entry.entry_id]["coordinator"] = coordinator
    await coordinator.async_config_entry_first_refresh()

    # Forward entry setup to the sensor platform
    await hass.config_entries.async_forward_entry_setups(entry, ["sensor"])

    return True


async def update_docker_status(hass: HomeAssistant, client, services, entry_id):
    """Fetch updated Docker container status and store in hass.data."""

    def get_all_containers_status():
        """Fetch status for all containers from Docker."""
        containers_status = {}

        try:
            containers = client.containers.list(all=True)

            for service_name in services:
                container_info = next(
                    (c.attrs for c in containers if c.name == service_name), None
                )

                if container_info:
                    containers_status[service_name] = {
                        "status": container_info.get("State", {}).get(
                            "Status", "unknown"
                        ),
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
                else:
                    containers_status[service_name] = {"status": "not_found"}

        except Exception as e:  # noqa: BLE001
            _LOGGER.error("Error fetching container status: %s", e)

        return containers_status

    if DOMAIN not in hass.data:
        hass.data[DOMAIN] = {}

    if entry_id not in hass.data[DOMAIN]:
        hass.data[DOMAIN][entry_id] = {}

    # Store updated status in hass.data for sensors to access
    hass.data[DOMAIN][entry_id]["status"] = await hass.async_add_executor_job(
        get_all_containers_status
    )

    return hass.data[DOMAIN][entry_id]["status"]


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Unload a config entry."""
    await hass.config_entries.async_forward_entry_unload(entry, "sensor")
    hass.data[DOMAIN].pop(entry.entry_id)
    return True
