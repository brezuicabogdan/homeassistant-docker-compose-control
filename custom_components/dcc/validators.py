"""Validation utilities for HA Docker Compose Control."""

import pathlib

import aiofiles
import voluptuous as vol
import yaml


async def validate_docker_socket(path: str) -> None:
    """Validate the Docker socket path."""
    if not pathlib.Path(path).exists():
        raise vol.Invalid("Docker socket path does not exist.")


async def validate_compose_file(path: str) -> None:
    """Validate the Docker Compose file path."""
    compose_path = pathlib.Path(path)
    if not compose_path.exists() or not compose_path.is_file():
        raise vol.Invalid("Compose file does not exist or is unreadable.")

    try:
        async with aiofiles.open(compose_path, encoding="UTF-8") as file:
            content = await file.read()
            compose_data = yaml.safe_load(content)
            if not isinstance(compose_data, dict) or "services" not in compose_data:
                raise vol.Invalid("Invalid Compose file: missing 'services' key.")  # noqa: TRY301
    except yaml.YAMLError as e:
        raise vol.Invalid("YAML error in Compose file.") from e
    except Exception as e:  # Catch any unexpected errors
        raise vol.Invalid(f"Error reading Compose file: {e!s}") from e
