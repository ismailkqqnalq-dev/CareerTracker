import asyncio

from sqlalchemy.exc import OperationalError

import app.main as main_module
import app.seed_skill_catalog as seed_module
from app.models.skills import Skill
from app.skill_catalog import SKILL_CATALOG
from tests.conftest import TestingSessionLocal


def _global_skill_count(db):
    return db.query(Skill).filter(Skill.owner_user_id.is_(None)).count()


def test_startup_fills_an_empty_catalog_once(db_session, monkeypatch):
    monkeypatch.setattr(seed_module, "SessionLocal", TestingSessionLocal)
    assert _global_skill_count(db_session) == 0

    seed_module.seed_catalog_on_startup()
    seeded = _global_skill_count(db_session)
    seed_module.seed_catalog_on_startup()

    assert seeded == len(SKILL_CATALOG)
    assert _global_skill_count(db_session) == seeded


def test_seeded_catalog_lets_a_user_add_a_profile_skill(authenticated_client, monkeypatch):
    monkeypatch.setattr(seed_module, "SessionLocal", TestingSessionLocal)
    seed_module.seed_catalog_on_startup()

    skills = authenticated_client.get("/skills?limit=200").json()
    python = next(skill for skill in skills if skill["name"] == "Python")
    response = authenticated_client.post(
        "/users/me/skills", json={"skill_id": python["id"], "proficiency_level": "intermediate"}
    )

    assert response.status_code in (200, 201), response.text


def test_startup_survives_a_database_without_tables(monkeypatch, caplog):
    class MissingTablesSession:
        def query(self, *_args, **_kwargs):
            raise OperationalError("SELECT", {}, Exception("no such table: skills"))

        def rollback(self):
            pass

        def close(self):
            pass

    monkeypatch.setattr(seed_module, "SessionLocal", MissingTablesSession)

    seed_module.seed_catalog_on_startup()

    assert "alembic upgrade head" in caplog.text


def test_application_startup_seeds_the_catalog(monkeypatch):
    calls = []
    monkeypatch.setattr(main_module, "seed_catalog_on_startup", lambda: calls.append(True))

    async def start_application():
        async with main_module.app.router.lifespan_context(main_module.app):
            pass

    asyncio.run(start_application())

    assert calls == [True]
