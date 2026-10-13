from datetime import date
from pathlib import Path

from sqlmodel import select

from youtopia import db, models
from youtopia.models import Completion, Domain, SkillLevel, Task, TaskStatus


def test_db_lives_under_override(tmp_path):
    assert db.db_path() == tmp_path / "youtopia-home" / "youtopia.db"
    db.get_engine()
    assert db.db_path().exists()


def test_default_location_is_home_dir(monkeypatch):
    monkeypatch.delenv(db.HOME_ENV_VAR)
    assert db.db_path() == Path.home() / ".youtopia" / "youtopia.db"


def test_task_and_completion_round_trip(session):
    task = Task(
        title="Sketch a mug",
        instructions="Draw the nearest mug in five minutes.",
        domain=Domain.PRODUCTION,
        difficulty=1,
        duration_minutes=5,
        done_criteria="One sketch exists.",
        offered_on=date(2026, 10, 13),
        slot=1,
    )
    session.add(task)
    session.flush()
    session.add(Completion(task_id=task.id, note="wonky handle"))
    session.commit()

    stored = session.exec(select(Task)).one()
    assert stored.status == TaskStatus.OFFERED
    assert stored.domain == Domain.PRODUCTION
    completion = session.exec(select(Completion)).one()
    assert completion.task_id == stored.id
    assert completion.completed_at is not None


def test_older_database_gains_new_skill_columns():
    import sqlite3

    path = db.db_path()
    path.parent.mkdir(parents=True)
    with sqlite3.connect(path) as conn:  # the M2 shape of the table
        conn.execute(
            "CREATE TABLE skilllevel (id INTEGER PRIMARY KEY, domain VARCHAR NOT NULL UNIQUE,"
            " level INTEGER NOT NULL, recent_successes INTEGER NOT NULL)"
        )
        conn.execute("INSERT INTO skilllevel VALUES (1, 'CREATIVE', 3, 2)")

    with db.session_scope() as session:
        skill = session.exec(select(SkillLevel)).one()
        assert (skill.level, skill.recent_successes) == (3, 2)
        assert (skill.recent_declines, skill.recent_misses, skill.last_evaluated) == (0, 0, None)
        assert skill.domain == Domain.PRODUCTION  # stored as CREATIVE before the area rename


def test_old_area_names_are_migrated():
    with db.session_scope() as session:  # creates the current schema
        session.add(
            Task(title="Old", instructions="i", domain=Domain.LABOUR, difficulty=1,
                 duration_minutes=5, done_criteria="d", offered_on=date(2026, 10, 1), slot=1)
        )  # fmt: skip
    import sqlite3

    with sqlite3.connect(db.db_path()) as conn:  # rewind to the old names
        conn.execute("UPDATE task SET domain = 'PHYSICAL'")
        conn.execute(
            "INSERT INTO skilllevel (domain, level, recent_successes, recent_declines,"
            " recent_misses) VALUES ('CARING', 4, 1, 0, 0)"
        )
        conn.execute(
            "INSERT INTO profile (interests, minutes_per_day, accessibility_limits,"
            " preferred_challenge, sincerity, humor, sarcasm, rudeness, created_at, updated_at)"
            " VALUES ('[\"physical\", \"problems\"]', 20, '[]', 2, 4, 1, 0, 0,"
            " '2026-10-01 00:00:00', '2026-10-01 00:00:00')"
        )
    db._engine_for.cache_clear()

    with db.session_scope() as session:
        assert session.exec(select(Task)).one().domain == Domain.LABOUR
        assert session.exec(select(SkillLevel)).one().domain == Domain.CARETAKING
        assert session.exec(select(models.Profile)).one().interests == ["labour", "tickets"]
