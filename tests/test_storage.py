from datetime import date
from pathlib import Path

from sqlmodel import select

from youtopia import db
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
        domain=Domain.CREATIVE,
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
    assert stored.domain == Domain.CREATIVE
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
