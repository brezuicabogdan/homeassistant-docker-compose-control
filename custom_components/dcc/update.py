"""Support for Docker service updates."""

import logging

import docker

from homeassistant.components.update import UpdateEntity

_LOGGER = logging.getLogger(__name__)


class DockerServiceUpdateEntity(UpdateEntity):
    """Representation of a Docker service update entity."""

    def __init__(self, client, service_name) -> None:
        """Initialize the Docker service update entity."""
        self._client = client
        self._service_name = service_name
        self._available = False

    @property
    def name(self):
        """Return the name of the entity."""
        return f"{self._service_name} Update"

    @property
    def available(self):
        """Return True if an update is available."""
        return self._available

    async def async_update(self):
        """Check if an update is available."""
        try:
            container = await self.hass.async_add_executor_job(
                self._client.containers.get, self._service_name
            )
            image = container.image
            if not image.tags:
                _LOGGER.warning("Container %s has no tagged images", self._service_name)
                self._available = False
                return

            updated_image = await self.hass.async_add_executor_job(
                self._client.images.pull, image.tags[0]
            )
            self._available = image.id != updated_image.id
        except docker.errors.NotFound:
            _LOGGER.warning("Container %s not found", self._service_name)
            self._available = False
        except Exception as e:  # noqa: BLE001
            _LOGGER.error("Error checking update for %s: %s", self._service_name, e)
            self._available = False
