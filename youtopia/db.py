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

DIR_MODE = 0o700
FILE_MODE = 0o600

# Columns added after a table was first released: {table: {column: ALTER statement}}.
# create_all() only creates missing tables, so older databases get these on startup.
# Every statement is a literal: no SQL is built from strings anywhere in YOUtopia.
ADDED_COLUMNS = {
    "skilllevel": {
        "recent_declines": (
            "ALTER TABLE skilllevel ADD COLUMN recent_declines INTEGER NOT NULL DEFAULT 0"
        ),
        "recent_misses": (
            "ALTER TABLE skilllevel ADD COLUMN recent_misses INTEGER NOT NULL DEFAULT 0"
        ),
        "last_evaluated": "ALTER TABLE skilllevel ADD COLUMN last_evaluated DATE",
    },
    "task": {
        # Enum values are stored by name.
        "source": "ALTER TABLE task ADD COLUMN source VARCHAR NOT NULL DEFAULT 'TEMPLATE'",
        "declined_at": "ALTER TABLE task ADD COLUMN declined_at DATETIME",
        "problem": "ALTER TABLE task ADD COLUMN problem JSON",
    },
}
RENAME_DOMAIN_STATEMENTS = (
    "UPDATE task SET domain = :new WHERE domain = :old",
    "UPDATE skilllevel SET domain = :new WHERE domain = :old",
)


def data_dir() -> Path:
    override = os.environ.get(HOME_ENV_VAR)
    return Path(override) if override else Path.home() / ".youtopia"


def db_path() -> Path:
    return data_dir() / DB_FILENAME


def ensure_private_dir(path: Path) -> Path:
    """Create the data folder readable only by you (0700), tightening an existing one."""
    path.mkdir(mode=DIR_MODE, parents=True, exist_ok=True)
    os.chmod(path, DIR_MODE)
    return path


def ensure_private_file(path: Path) -> Path:
    """Create a file readable only by you (0600), tightening an existing one."""
    if not path.exists():
        os.close(os.open(path, os.O_WRONLY | os.O_CREAT, FILE_MODE))
    os.chmod(path, FILE_MODE)
    return path


@cache
def _engine_for(path: Path) -> Engine:
    ensure_private_dir(path.parent)
    ensure_private_file(path)  # SQLite gives its journal files the database's permissions
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
            for name, statement in columns.items():
                if name not in existing:
                    conn.execute(text(statement))


def _rename_domains(engine: Engine) -> None:
    """Move stored data from the old area names to the current ones. Safe to rerun."""
    renames = {old.upper(): new.name for old, new in models.LEGACY_DOMAIN_NAMES.items()}
    with engine.begin() as conn:
        for statement in RENAME_DOMAIN_STATEMENTS:
            for old, new in renames.items():
                conn.execute(text(statement), {"new": new, "old": old})
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
