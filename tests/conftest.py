from collections.abc import Iterator

import pytest
from sqlmodel import Session

from youtopia import db


@pytest.fixture(autouse=True)
def temp_home(tmp_path, monkeypatch) -> Iterator[None]:
    """Point every test at a fresh database under tmp_path, never ~/.youtopia."""
    monkeypatch.setenv(db.HOME_ENV_VAR, str(tmp_path / "youtopia-home"))
    yield
    db._engine_for.cache_clear()


@pytest.fixture
def session() -> Iterator[Session]:
    with db.session_scope() as s:
        yield s
