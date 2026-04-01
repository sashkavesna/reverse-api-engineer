"""State manager (Vault) for handling browser profiles and cookies."""

import json
import re
from pathlib import Path

import httpx

# Only used for type hinting to avoid requiring playwright at runtime for API clients
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from playwright.async_api import BrowserContext

from .utils import get_app_dir


class ProfileNotFoundError(Exception):
    """Raised when a requested profile does not exist in the vault."""
    pass


class SessionExpiredError(Exception):
    """Raised when a profile's session (cookies) has expired and returns 401/403."""
    pass


def get_profiles_dir() -> Path:
    """Get the directory where browser profiles are stored."""
    profiles_dir = get_app_dir() / "profiles"
    profiles_dir.mkdir(parents=True, exist_ok=True)
    return profiles_dir


def _validate_profile_name(name: str) -> str:
    """Validate and sanitize profile name."""
    if not name:
        raise ValueError("Profile name cannot be empty")

    # Only allow alphanumeric, dash, and underscore
    if not re.match(r"^[a-zA-Z0-9_-]+$", name):
        raise ValueError(
            f"Invalid profile name: '{name}'. "
            "Only alphanumeric characters, hyphens, and underscores are allowed"
        )

    return name


def save_profile(name: str, context: 'BrowserContext') -> Path:
    """Save the Playwright browser context state to the vault.

    Args:
        name: The name of the profile
        context: The Playwright BrowserContext to save

    Returns:
        Path to the saved state file
    """
    name = _validate_profile_name(name)
    profile_path = get_profiles_dir() / f"{name}.json"

    # Playwright's storage_state extracts cookies and localStorage
    state = context.storage_state()

    with open(profile_path, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2)

    return profile_path


def load_profile(name: str) -> httpx.Cookies:
    """Load a profile from the vault and return it as httpx.Cookies.

    Args:
        name: The name of the profile to load

    Returns:
        httpx.Cookies object ready to be passed to httpx.Client()

    Raises:
        ProfileNotFoundError: If the profile does not exist
        ValueError: If the profile file is corrupted or invalid
    """
    name = _validate_profile_name(name)
    profile_path = get_profiles_dir() / f"{name}.json"

    if not profile_path.exists():
        raise ProfileNotFoundError(
            f'Profile "{name}" not found. '
            f'Run "reverse-api-engineer vault auth {name}" to create it.'
        )

    try:
        with open(profile_path, "r", encoding="utf-8") as f:
            state = json.load(f)
    except json.JSONDecodeError as e:
        raise ValueError(f'Profile "{name}" is corrupted (invalid JSON).') from e

    if "cookies" not in state:
        raise ValueError(f'Profile "{name}" does not contain valid cookie data.')

    # Convert Playwright cookies format to httpx.Cookies
    httpx_cookies = httpx.Cookies()
    for cookie in state.get("cookies", []):
        httpx_cookies.set(
            cookie["name"],
            cookie["value"],
            domain=cookie.get("domain", ""),
            path=cookie.get("path", "/")
        )

    return httpx_cookies


def list_profiles() -> list[dict]:
    """List all saved profiles with metadata.

    Returns:
        List of dicts with keys: name, path, cookie_count, domains, modified
    """
    profiles_dir = get_profiles_dir()
    results = []

    for profile_path in sorted(profiles_dir.glob("*.json")):
        try:
            with open(profile_path, "r", encoding="utf-8") as f:
                state = json.load(f)

            cookies = state.get("cookies", [])
            domains = sorted(set(c.get("domain", "").lstrip(".") for c in cookies if c.get("domain")))

            results.append({
                "name": profile_path.stem,
                "path": profile_path,
                "cookie_count": len(cookies),
                "domains": domains,
                "modified": profile_path.stat().st_mtime,
            })
        except (json.JSONDecodeError, KeyError):
            results.append({
                "name": profile_path.stem,
                "path": profile_path,
                "cookie_count": 0,
                "domains": [],
                "modified": profile_path.stat().st_mtime,
            })

    return results


def delete_profile(name: str) -> Path:
    """Delete a profile from the vault.

    Args:
        name: The name of the profile to delete

    Returns:
        Path of the deleted file

    Raises:
        ProfileNotFoundError: If the profile does not exist
    """
    name = _validate_profile_name(name)
    profile_path = get_profiles_dir() / f"{name}.json"

    if not profile_path.exists():
        raise ProfileNotFoundError(
            f'Profile "{name}" not found.'
        )

    profile_path.unlink()
    return profile_path
