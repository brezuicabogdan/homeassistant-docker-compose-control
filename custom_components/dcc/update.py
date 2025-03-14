"""Integration for Docker Service Update Entity."""

from datetime import timedelta
import logging

import aiohttp
import docker

from homeassistant.components.update import UpdateEntity, UpdateEntityFeature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.event import async_call_later

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry, async_add_entities):
    """Set up Docker service update entities."""
    _LOGGER.debug("Setting up Docker update entities for entry: %s", entry.entry_id)

    data = hass.data[DOMAIN].get(entry.entry_id)
    if not data:
        _LOGGER.error("No data found for entry %s", entry.entry_id)
        return

    client = data.get("client")
    services = data.get("services")
    update_interval = data.get("container_image_update_check_interval")

    if not client or not services:
        _LOGGER.error("Missing client or services for entry %s", entry.entry_id)
        return

    update_entities = [
        DockerServiceUpdateEntity(
            hass, service_name, container_name, client, update_interval
        )
        for service_name, container_name in services.items()
    ]

    async_add_entities(update_entities)

    for entity in update_entities:
        await entity.async_update()
        entity.async_write_ha_state()

    _LOGGER.info("Successfully added update entities for entry: %s", entry.entry_id)


class DockerServiceUpdateEntity(UpdateEntity):
    """Representation of a Docker service update entity."""

    _attr_supported_features = UpdateEntityFeature.INSTALL
    _attr_has_entity_name = True

    def __init__(
        self, hass: HomeAssistant, service_name, container_name, client, update_interval
    ) -> None:
        """Initialize the update entity."""
        self._hass = hass
        self._service_name = service_name
        self._container_name = container_name
        self._client = client
        self._update_interval = update_interval
        self._installed_version = None
        self._latest_version = None
        self._available = False
        self._image_repository = None

        self._attr_unique_id = f"{DOMAIN}_{self._service_name}_update"
        self._attr_name = f"{self._service_name} Update"

        _LOGGER.info(
            "Scheduling periodic update checks for %s every %s hours",
            self._service_name,
            self._update_interval,
        )
        async_call_later(
            self._hass, timedelta(hours=self._update_interval), self._schedule_update
        )

    async def _schedule_update(self, _):
        """Perform update and re-schedule the next check."""
        await self.async_update()
        async_call_later(
            self._hass, timedelta(hours=self._update_interval), self._schedule_update
        )

    @property
    def installed_version(self):
        """Return the currently installed version."""
        return self._installed_version

    @property
    def latest_version(self):
        """Return the latest available version."""
        return self._latest_version

    @property
    def available(self):
        """Return if the update is available."""
        return self._available

    async def async_update(self):
        """Fetch the latest version and update availability."""
        _LOGGER.info("Checking for updates for %s", self._service_name)

        try:
            container_name = None
            all_containers = await self._hass.async_add_executor_job(
                self._client.containers.list, True
            )

            # 🔹 Perform case-insensitive matching
            for container in all_containers:
                if container.name.lower() == self._container_name.lower():
                    container_name = container.name
                    break

            if not container_name:
                _LOGGER.error(
                    "Container %s not found, skipping update check",
                    self._container_name,
                )
                self._installed_version = "unknown"
                self._available = False
                self.async_write_ha_state()
                return

            _LOGGER.info("Matched container name: %s", container_name)
            container = await self._hass.async_add_executor_job(
                self._client.containers.get, container_name
            )

            repo_digests = await self._hass.async_add_executor_job(
                lambda: container.image.attrs.get("RepoDigests", [])
            )

            if not repo_digests:
                _LOGGER.error(
                    "No RepoDigests found for %s, skipping update check",
                    self._container_name,
                )
                self._installed_version = "unknown"
                self._latest_version = "unknown"
                self._available = False
                self.async_write_ha_state()
                return

            repo_name, installed_sha = repo_digests[0].split("@")

            if "/" not in repo_name:  # If no registry prefix, assume docker.io
                repo_name = f"docker.io/{repo_name}"

            self._image_repository = repo_name
            self._installed_version = installed_sha

        except docker.errors.NotFound:
            _LOGGER.error(
                "Container %s not found, skipping update check", self._container_name
            )
            self._installed_version = "unknown"
            self._available = False
            self.async_write_ha_state()
            return
        except Exception as e:
            _LOGGER.error(
                "Error inspecting container %s: %s", self._container_name, str(e)
            )
            self._installed_version = "unknown"
            self._available = False
            self.async_write_ha_state()
            return

        self._latest_version = await RegistryManager.get_latest_image_sha(
            self._image_repository
        )
        self._available = self._latest_version not in {
            None,
            "unknown",
            self._installed_version,
        }

        _LOGGER.debug(
            "Service %s: Installed SHA %s, Latest SHA %s, Available %s",
            self._service_name,
            self._installed_version,
            self._latest_version,
            self._available,
        )

        self.async_write_ha_state()


class RegistryManager:
    """Manages multiple registry handlers."""

    @staticmethod
    async def get_latest_image_sha(image_name):
        """Fetch the latest image SHA from the appropriate registry."""
        if image_name.startswith("ghcr.io"):
            _LOGGER.debug("Processing %s with repo: ghcr.io", image_name)
            return await GHCRRegistryHandler.get_latest_sha(image_name)

        _LOGGER.debug("Processing %s with repo: docker.io", image_name)
        return await DockerHubRegistryHandler.get_latest_sha(image_name)


class DockerHubRegistryHandler:
    """Handler for Docker Hub registry."""

    @staticmethod
    async def get_latest_sha(image_name):
        """Fetch latest image SHA from Docker Hub."""

        # 🔹 Remove 'docker.io/' prefix if present
        if image_name.startswith("docker.io/"):
            image_name = image_name.replace("docker.io/", "")

        # 🔹 Try two possible repository formats
        possible_urls = [
            f"https://hub.docker.com/v2/repositories/{image_name}/tags/latest",
            f"https://hub.docker.com/v2/repositories/library/{image_name}/tags/latest",
        ]

        headers = {}

        async with aiohttp.ClientSession() as session:
            for registry_url in possible_urls:
                async with session.get(
                    registry_url, timeout=10, headers=headers
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        latest_sha = data.get("images", [{}])[0].get(
                            "digest", "unknown"
                        )
                        _LOGGER.info(
                            "[docker.io] Latest SHA for %s is %s",
                            image_name,
                            latest_sha,
                        )
                        return latest_sha
                    elif response.status == 404:
                        _LOGGER.warning(
                            "[docker.io] Repository %s not found at %s",
                            image_name,
                            registry_url,
                        )
                    else:
                        _LOGGER.error(
                            "[docker.io] Failed to fetch latest image SHA, HTTP %s",
                            response.status,
                        )

        _LOGGER.error("[docker.io] Could not find repository for image: %s", image_name)
        return "unknown"


class GHCRRegistryHandler:
    """Handler for GitHub Container Registry (GHCR) without authentication token."""

    @staticmethod
    async def get_latest_sha(image_name):
        """Fetch latest image SHA from GHCR without authentication."""
        repo_name = image_name.replace("ghcr.io/", "")

        # Step 1: Get an access token
        token_url = f"https://ghcr.io/token?scope=repository:{repo_name}:pull"
        async with (
            aiohttp.ClientSession() as session,
            session.get(token_url, timeout=10) as response,
        ):
            if response.status != 200:
                _LOGGER.error(
                    "[ghcr.io] Failed to get GHCR token, HTTP %s", response.status
                )
                return "unknown"

            token_data = await response.json()
            access_token = token_data.get("token")

        if not access_token:
            _LOGGER.error("[ghcr.io] GHCR did not return a valid token")
            return "unknown"

        # Step 2: Get the list of available tags
        tags_url = f"https://ghcr.io/v2/{repo_name}/tags/list"
        headers = {"Authorization": f"Bearer {access_token}"}

        async with (
            aiohttp.ClientSession() as session,
            session.get(tags_url, timeout=10, headers=headers) as response,
        ):
            if response.status != 200:
                _LOGGER.error(
                    "[ghcr.io] Failed to fetch tags, HTTP %s", response.status
                )
                return "unknown"

            tags_data = await response.json()
            tags = tags_data.get("tags", [])

        if not tags:
            _LOGGER.error("[ghcr.io] No tags found for %s", image_name)
            return "unknown"

        latest_tag = sorted(tags)[-1]  # Get the latest tag

        _LOGGER.info("[ghcr.io] Using latest tag: %s for %s", latest_tag, image_name)

        # Step 3: Get the manifest for the latest tag
        manifest_url = f"https://ghcr.io/v2/{repo_name}/manifests/{latest_tag}"
        headers["Accept"] = "application/vnd.docker.distribution.manifest.v2+json"

        async with (
            aiohttp.ClientSession() as session,
            session.get(manifest_url, timeout=10, headers=headers) as response,
        ):
            if response.status != 200:
                _LOGGER.error(
                    "[ghcr.io] Failed to fetch manifest, HTTP %s", response.status
                )
                return "unknown"

            manifest_data = await response.json()

        # Step 4: Extract the SHA digest
        latest_sha = manifest_data.get("config", {}).get("digest")
        if not latest_sha:
            latest_sha = manifest_data.get("layers", [{}])[0].get("digest")
        if not latest_sha:
            latest_sha = manifest_data.get("manifests", [{}])[0].get("digest")

        if not latest_sha:
            _LOGGER.error("[ghcr.io] Could not extract SHA for %s", image_name)
            return "unknown"

        _LOGGER.info("[ghcr.io] Latest SHA for %s is %s", image_name, latest_sha)
        return latest_sha
