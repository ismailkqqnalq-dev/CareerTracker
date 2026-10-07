from app.services.skill_normalizer import find_skill, normalize_text
import pytest
from app.database.session import SessionLocal
from app.models.skills import Skill, SkillAliases
from app.services.skill_service import create_skill

def _cleanup(db, name: str, alias: str)-> None:
    db.rollback()
    db.query(SkillAliases).filter(SkillAliases.alias == alias).delete()
    db.query(Skill).filter(Skill.name == name).delete()
    db.commit()
    
def test_create_skill_makes_skill_findable_by_its_own_name():
    sessions = SessionLocal()
    try:
        created = create_skill(sessions, "Test Skill X")
        found = find_skill(sessions, "Test Skill X")
        assert found is not None
        assert found.id == created.id
    finally:
        _cleanup(sessions, "Test Skill X", "test skill x")
        sessions.close()
        
def test_create_skill_duplicate_raises_value_error():
    sessions = SessionLocal()
    try:
        create_skill(sessions, "Test Skill Y")
        with pytest.raises(ValueError):
            create_skill(sessions, "   test SKILL y   ")
    finally:
        _cleanup(sessions, "Test Skill Y", "test skill y")
        sessions.close()