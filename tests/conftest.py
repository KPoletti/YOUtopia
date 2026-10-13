import os
import socket
from collections.abc import Iterator

import keyring
import pytest
from keyring.backend import KeyringBackend
from keyring.errors import PasswordDeleteError
from sqlmodel import Session

from youtopia import db, secrets
from youtopia.providers.catalog import PROVIDERS

LIVE = os.environ.get("YOUTOPIA_LIVE_TESTS") == "1"


class MemoryKeyring(KeyringBackend):
    priority = 1

    def __init__(self) -> None:
        super().__init__()
        self.store: dict[tuple[str, str], str] = {}

    def get_password(self, service, username):
        return self.store.get((service, username))

    def set_password(self, service, username, password):
        self.store[(service, username)] = password

    def delete_password(self, service, username):
        if self.store.pop((service, username), None) is None:
            raise PasswordDeleteError("not found")


@pytest.fixture(autouse=True)
def temp_home(tmp_path, monkeypatch) -> Iterator[None]:
    """Point every test at a fresh database under tmp_path, never ~/.youtopia."""
    monkeypatch.setenv(db.HOME_ENV_VAR, str(tmp_path / "youtopia-home"))
    yield
    db._engine_for.cache_clear()


@pytest.fixture(autouse=True)
def no_network(monkeypatch) -> None:
    """Tests never reach the network; live tests opt out with YOUTOPIA_LIVE_TESTS=1."""
    if LIVE:
        return

    def blocked(*args, **kwargs):
        raise RuntimeError("Network access is blocked in tests")

    monkeypatch.setattr(socket.socket, "connect", blocked)
    monkeypatch.setattr(socket.socket, "connect_ex", blocked)
    monkeypatch.setattr(socket, "create_connection", blocked)
    monkeypatch.setattr(socket, "getaddrinfo", blocked)


@pytest.fixture(autouse=True)
def memory_keyring(monkeypatch) -> Iterator[MemoryKeyring]:
    """A fresh in-memory keyring, and no real API keys from the developer's environment."""
    if not LIVE:
        for var in {secrets.GENERIC_ENV} | {s.key_env for s in PROVIDERS.values() if s.key_env}:
            monkeypatch.delenv(var, raising=False)
    previous = keyring.get_keyring()
    backend = MemoryKeyring()
    keyring.set_keyring(backend)
    yield backend
    keyring.set_keyring(previous)


@pytest.fixture
def session() -> Iterator[Session]:
    with db.session_scope() as s:
        yield s
