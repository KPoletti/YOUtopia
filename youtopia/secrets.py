"""API key lookup: environment variables first, then the OS keyring.

Keys are never written to config or the database, never logged, and only ever shown
masked to their last four characters.
"""

import os
from dataclasses import dataclass

import keyring
from keyring.errors import KeyringError, PasswordDeleteError

from youtopia.providers.catalog import PROVIDERS

KEYRING_SERVICE = "youtopia"
GENERIC_ENV = "YOUTOPIA_API_KEY"
MASK = "••••"
# Keys shorter than this are shown fully masked, so the visible part stays a small fraction.
MIN_LENGTH_TO_SHOW_TAIL = 12


class KeyringUnavailable(Exception):
    """No usable OS keyring backend (common on headless Linux and WSL)."""


@dataclass(frozen=True)
class FoundKey:
    value: str
    source: str  # e.g. "env YOUTOPIA_API_KEY" or "keyring"

    def __repr__(self) -> str:
        return f"FoundKey(source={self.source!r}, value={mask(self.value)!r})"

    __str__ = __repr__

    @property
    def masked(self) -> str:
        return mask(self.value)


def mask(key: str) -> str:
    """Show at most the last four characters."""
    if len(key) < MIN_LENGTH_TO_SHOW_TAIL:
        return MASK
    return MASK + key[-4:]


def env_vars_for(provider: str) -> list[str]:
    spec = PROVIDERS.get(provider)
    own = [spec.key_env] if spec and spec.key_env else []
    return [GENERIC_ENV, *own]


def key_in_env(provider: str) -> bool:
    return any(os.environ.get(var, "").strip() for var in env_vars_for(provider))


def find_key(provider: str) -> FoundKey | None:
    """YOUTOPIA_API_KEY, then the provider's own variable, then the keyring."""
    for var in env_vars_for(provider):
        if value := os.environ.get(var, "").strip():
            return FoundKey(value, f"env {var}")
    try:
        value = keyring.get_password(KEYRING_SERVICE, provider)
    except KeyringError:
        return None
    return FoundKey(value, "keyring") if value else None


def set_key(provider: str, value: str) -> None:
    try:
        keyring.set_password(KEYRING_SERVICE, provider, value)
    except KeyringError as err:
        raise KeyringUnavailable(str(err)) from None


def remove_key(provider: str) -> bool:
    """Remove the keyring entry. Returns False if there was none."""
    try:
        if keyring.get_password(KEYRING_SERVICE, provider) is None:
            return False
        keyring.delete_password(KEYRING_SERVICE, provider)
    except PasswordDeleteError:
        return False
    except KeyringError as err:
        raise KeyringUnavailable(str(err)) from None
    return True
