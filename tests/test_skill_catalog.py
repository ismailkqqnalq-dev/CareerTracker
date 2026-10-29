import os
import subprocess
import sys

import pytest

from app.database.session import get_db
from app.main import app
from app.models.skills import Skill, SkillAliases
from app.services.skill_catalog_service import seed_skill_catalog
from app.services.skill_normalizer import find_skill
from app.skill_catalog import SKILL_CATALOG


@pytest.fixture()
def db_session(client):
    db_generator = app.dependency_overrides[get_db]()
    db = next(db_generator)
    try:
        yield db
    finally:
        db_generator.close()


def test_seed_skill_catalog_is_idempotent(db_session):
    first_result = seed_skill_catalog(db_session)
    second_result = seed_skill_catalog(db_session)

    expected_alias_count = sum(
        1 + len(entry["aliases"])
        for entry in SKILL_CATALOG
    )

    assert first_result == {
        "skills_created": len(SKILL_CATALOG),
        "aliases_created": expected_alias_count,
    }
    assert second_result == {
        "skills_created": 0,
        "aliases_created": 0,
    }


def test_seed_entrypoint_registers_user_metadata_on_fresh_database(tmp_path):
    database_path = tmp_path / "fresh-seed.db"
    script = """
from app.seed_skill_catalog import main
from app.database.session import Base, SessionLocal, engine
Base.metadata.create_all(bind=engine)
from app.models.users import User
from app.models.skills import PersonalSkillAlias, Skill
with SessionLocal() as db:
    user = User(email='seed-user@example.test', hashed_password='unused')
    db.add(user)
    db.flush()
    private_skill = Skill(name='Private seed fixture', category='tool', owner_user_id=user.id)
    db.add(private_skill)
    db.flush()
    alias = PersonalSkillAlias(user_id=user.id, alias='private seed alias', skill_id=private_skill.id)
    db.add(alias)
    db.commit()
main()
main()
with SessionLocal() as db:
    assert db.query(User).filter_by(email='seed-user@example.test').count() == 1
    assert db.query(Skill).filter_by(name='Private seed fixture').count() == 1
    assert db.query(PersonalSkillAlias).filter_by(alias='private seed alias').count() == 1
"""
    env = os.environ.copy()
    env["DATABASE_URL"] = f"sqlite:///{database_path.as_posix()}"
    env["PYTHON_DOTENV_DISABLED"] = "1"

    result = subprocess.run(
        [sys.executable, "-c", script],
        capture_output=True,
        text=True,
        env=env,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert "Skill catalog seeded: 12 skills, 34 aliases added." in result.stdout
    assert "Skill catalog seeded: 0 skills, 0 aliases added." in result.stdout


def test_catalog_aliases_resolve_to_canonical_skill(db_session):
    seed_skill_catalog(db_session)

    python = find_skill(db_session, "  PY  ")
    postgres = find_skill(db_session, "Postgres")
    kubernetes = find_skill(db_session, "K8S")

    assert python is not None
    assert python.name == "Python"

    assert postgres is not None
    assert postgres.name == "PostgreSQL"

    assert kubernetes is not None
    assert kubernetes.name == "Kubernetes"


def test_seed_catalog_rejects_alias_owned_by_another_skill(db_session):
    other_skill = Skill(name="Unrelated Skill", category="other")
    db_session.add(other_skill)
    db_session.flush()
    db_session.add(
        SkillAliases(alias="py", skill_id=other_skill.id)
    )
    db_session.commit()

    with pytest.raises(ValueError, match="already belongs to another skill"):
        seed_skill_catalog(db_session)

    db_session.expire_all()
    assert (
        db_session.query(Skill)
        .filter(Skill.name == "Python")
        .first()
        is None
    )
