"""Sensor platform for HA Docker Compose Control."""

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import DOMAIN

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities
):
    """Set up the sensors from a config entry."""
    data = hass.data[DOMAIN][entry.entry_id]
    client = data["client"]
    services = data["services"]
    coordinator = data["coordinator"]

    entities = [DCCSensor(coordinator, entry, client, service) for service in services]
    async_add_entities(entities, update_before_add=True)


class DCCSensor(CoordinatorEntity, Entity):
    """Representation of a HA Docker Compose Control sensor."""

    def __init__(self, coordinator, entry: ConfigEntry, client, service_name) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)

        self.entry_id = entry.entry_id
        self.client = client
        self.service_name = service_name
        self._attr_name = service_name
        self._attr_unique_id = f"ha_dcc_{entry.entry_id}_{service_name}"
        self._state = None
        self._attributes = {}

        compose_file = entry.data.get("compose_file", "Unknown Compose File")
        docker_socket = entry.data.get("docker_socket", "Unknown Docker Socket")
        device_name = f"{compose_file} on {docker_socket}"

        # Link entity to the config entry device
        self._attr_device_info = {
            "identifiers": {(DOMAIN, self.entry_id)},
            "name": device_name,
            "manufacturer": "BreziCode",
            "model": "Docker Compose",
        }

    async def async_update(self):
        """Fetch the latest state from Docker asynchronously."""
        try:

            def get_container_info():
                container = self.client.containers.get(self.service_name)
                container_info = container.attrs
                return {
                    "status": container.status,  # Running, Exited, etc.
                    "health": container_info.get("State", {})
                    .get("Health", {})
                    .get("Status", "unknown"),
                    "restart_count": container_info.get("RestartCount", 0),
                    "image": container_info.get("Config", {}).get("Image", "unknown"),
                    "uptime": container_info.get("State", {}).get(
                        "StartedAt", "unknown"
                    ),
                }

            # Get updated container info
            container_data = await self.hass.async_add_executor_job(get_container_info)

            # Update state and attributes
            self._state = container_data.get("status")

            self._attributes.update(
                {
                    "health": container_data.get("health"),
                    "restart_count": container_data.get("restart_count"),
                    "image": container_data.get("image"),
                    "uptime": container_data.get("uptime"),
                }
            )

        except Exception as e:  # noqa: BLE001
            _LOGGER.error(
                "Failed to get container status for %s: %s", self.service_name, e
            )
            self._state = "unknown"
            self._attributes = {}

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

    @property
    def extra_state_attributes(self):
        """Return extra attributes of the sensor."""
        return self._attributes
