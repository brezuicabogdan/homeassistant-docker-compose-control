"""Sensor platform for HA Docker Compose Control."""

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities
):
    """Set up the sensors from a config entry."""
    data = hass.data[DOMAIN][entry.entry_id]
    coordinator = data["coordinator"]
    services = data["services"]

    entities = [DCCSensor(coordinator, entry, service) for service in services]
    async_add_entities(entities, update_before_add=True)


class DCCSensor(CoordinatorEntity, Entity):
    """Representation of a Docker container sensor."""

    def __init__(self, coordinator, entry: ConfigEntry, service_name) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)

        self.coordinator = coordinator  # Ensure it's properly stored

        self.entry_id = entry.entry_id
        self.service_name = service_name
        self._attr_name = f"Docker {service_name}"
        self._attr_unique_id = f"dcc_{entry.entry_id}_{service_name}"

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

    @property
    def state(self):
        """Return the state of the sensor."""
        return self.coordinator.data.get(self.service_name, {}).get("status", "unknown")

    @property
    def extra_state_attributes(self):
        """Return extra attributes of the sensor."""
        container_data = self.coordinator.data.get(self.service_name, {})

        return {
            "container_name": self.service_name,
            "entry_id": self.entry_id,
            "health": container_data.get("health"),
            "restart_count": container_data.get("restart_count"),
            "image": container_data.get("image"),
            "uptime": container_data.get("uptime"),
        }
