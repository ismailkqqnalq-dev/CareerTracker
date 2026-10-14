"""Exercise Alembic against disposable databases, never the development DB."""

import os
from pathlib import Path
import subprocess
import sys

import pytest
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from sqlalchemy import create_engine, inspect, text

from app.database.session import Base
from app.models.activities import Activity
from app.models.contacts import Contact
from app.models.opportunity import Opportunity
from app.models.opportunity_skills import OpportunitySkill
from app.models.skills import Skill, SkillAliases, UserSkill
from app.models.tasks import Task
from app.models.users import User

ROOT = Path(__file__).resolve().parents[1]
BASE_TABLES = {"opportunities", "contacts", "activities", "tasks"}
SKILL_TABLES = {"skills", "skill_aliases", "opportunity_skills"}
PRE_USER_TABLES = BASE_TABLES | SKILL_TABLES
ALL_TABLES = PRE_USER_TABLES | {"users", "user_skills"}


INITIAL = "d0fe616da34f"
PRE_USER_HEAD = "b3b24fd6d532"
HEAD = "64aa267fb63d"

def _alembic(url, *args):
    env = os.environ.copy()
    env["DATABASE_URL"] = url
    result = subprocess.run(
        [sys.executable, "-m", "alembic", *args],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr


def test_fresh_database_upgrade_downgrade_and_model_parity(tmp_path):
    url = "sqlite:///" + (tmp_path / "fresh.db").as_posix()
    engine = create_engine(url)
    try:
        _alembic(url, "upgrade", INITIAL)
        assert set(inspect(engine).get_table_names()) == BASE_TABLES | {"alembic_version"}

        _alembic(url, "upgrade", "head")
        assert set(inspect(engine).get_table_names()) == ALL_TABLES | {"alembic_version"}
        with engine.connect() as connection:
            assert compare_metadata(MigrationContext.configure(connection), Base.metadata) == []

        _alembic(url, "downgrade", "base")
        assert set(inspect(engine).get_table_names()) == {"alembic_version"}
        _alembic(url, "upgrade", "head")
        assert set(inspect(engine).get_table_names()) == ALL_TABLES | {"alembic_version"}
    finally:
        engine.dispose()



@pytest.mark.parametrize("revision", [INITIAL, PRE_USER_HEAD])
def test_existing_versioned_database_keeps_its_data(tmp_path, revision):
    url = "sqlite:///" + (tmp_path / "existing.db").as_posix()
    engine = create_engine(url)
    try:
        _alembic(url, "upgrade", revision)
        with engine.begin() as connection:
            connection.execute(
                Opportunity.__table__.insert().values(
                    id=1,
                    company="Existing company",
                )
            )

        _alembic(url, "upgrade", "head")

        with engine.connect() as connection:
            assert connection.execute(
                text("SELECT company FROM opportunities WHERE id = 1")
            ).scalar_one() == "Existing company"
            assert connection.execute(
                text("SELECT version_num FROM alembic_version")
            ).scalar_one() == HEAD
            assert compare_metadata(
                MigrationContext.configure(connection),
                Base.metadata,
            ) == []
    finally:
        engine.dispose()
