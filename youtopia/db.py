"""Database engine and session setup.

The database lives at ``~/.youtopia/youtopia.db`` by default. Set ``YOUTOPIA_HOME``
to use a different directory (tests do this to stay away from the real one).
"""

import json
import os
from collections.abc import Iterator
from contextlib import contextmanager
from functools import cache
from pathlib import Path

from sqlalchemy import Engine, inspect, text
from sqlmodel import Session, SQLModel, create_engine

from youtopia import models  # registers tables on SQLModel.metadata

HOME_ENV_VAR = "YOUTOPIA_HOME"
DB_FILENAME = "youtopia.db"

# Columns added after a table was first released: {table: {column: SQL definition}}.
# create_all() only creates missing tables, so older databases get these via ALTER TABLE.
ADDED_COLUMNS = {
    "skilllevel": {
        "recent_declines": "INTEGER NOT NULL DEFAULT 0",
        "recent_misses": "INTEGER NOT NULL DEFAULT 0",
        "last_evaluated": "DATE",
    },
    "task": {
        "source": "VARCHAR NOT NULL DEFAULT 'TEMPLATE'",  # enum values are stored by name
        "declined_at": "DATETIME",
        "problem": "JSON",
    },
}


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
    _add_missing_columns(engine)
    _rename_domains(engine)
    return engine


def _add_missing_columns(engine: Engine) -> None:
    inspector = inspect(engine)
    with engine.begin() as conn:
        for table, columns in ADDED_COLUMNS.items():
            existing = {c["name"] for c in inspector.get_columns(table)}
            for name, definition in columns.items():
                if name not in existing:
                    # Names and definitions are the constants above, never user input.
                    conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {name} {definition}"))


def _rename_domains(engine: Engine) -> None:
    """Move stored data from the old area names to the current ones. Safe to rerun."""
    renames = {old.upper(): new.name for old, new in models.LEGACY_DOMAIN_NAMES.items()}
    with engine.begin() as conn:
        for table in ("task", "skilllevel"):
            for old, new in renames.items():
                conn.execute(
                    text(f"UPDATE {table} SET domain = :new WHERE domain = :old"),
                    {"new": new, "old": old},
                )
        for profile_id, raw in conn.execute(text("SELECT id, interests FROM profile")).all():
            interests = json.loads(raw)
            updated = [
                models.LEGACY_DOMAIN_NAMES[i].value if i in models.LEGACY_DOMAIN_NAMES else i
                for i in interests
            ]
            if updated != interests:
                conn.execute(
                    text("UPDATE profile SET interests = :interests WHERE id = :id"),
                    {"interests": json.dumps(updated), "id": profile_id},
                )


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
