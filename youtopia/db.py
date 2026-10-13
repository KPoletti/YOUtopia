"""Database engine and session setup.

The database lives at ``~/.youtopia/youtopia.db`` by default. Set ``YOUTOPIA_HOME``
to use a different directory (tests do this to stay away from the real one).
"""

import os
from collections.abc import Iterator
from contextlib import contextmanager
from functools import cache
from pathlib import Path

from sqlalchemy import Engine
from sqlmodel import Session, SQLModel, create_engine

from youtopia import models  # noqa: F401  (registers tables on SQLModel.metadata)

HOME_ENV_VAR = "YOUTOPIA_HOME"
DB_FILENAME = "youtopia.db"


def data_dir() -> Path:
    override = os.environ.get(HOME_ENV_VAR)
    return Path(override) if override else Path.home() / ".youtopia"


def db_path() -> Path:
    return data_dir() / DB_FILENAME


@cache
def _engine_for(path: Path) -> Engine:
    path.parent.mkdir(parents=True, exist_ok=True)
    engine = create_engine(f"sqlite:///{path}")
    SQLModel.metadata.create_all(engine)
    return engine


def get_engine() -> Engine:
    return _engine_for(db_path())


@contextmanager
def session_scope() -> Iterator[Session]:
    """Yield a session that commits on success and rolls back on error."""
    with Session(get_engine()) as session:
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
