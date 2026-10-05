from app.models.skills import Skill
from app.models.skills import SkillAliases
from app.database import session

import pytest
from sqlalchemy.exc import IntegrityError

def test_duplicate_skill_name_raises_integrity_error():
    
    sessions = session.SessionLocal()
    
    try:
        sessions.add(Skill(name="Test Skill"))
        sessions.commit()
        sessions.add(Skill(name="Test Skill"))
        with pytest.raises(IntegrityError):
            sessions.commit()
    finally:
        sessions.rollback()
        sessions.query(Skill).filter(Skill.name == "Test Skill").delete()
        sessions.commit()
        sessions.close()

def test_duplicate_skill_alias_raises_integrity_error():
    sessions = session.SessionLocal()
    
    try:
        skill = Skill(name="Test Skill for Alias")
        sessions.add(skill)
        sessions.commit()
        alias1 = SkillAliases(alias="Test Alias", skill_id=skill.id)
        sessions.add(alias1)
        sessions.commit()
        alias2 = SkillAliases(alias="Test Alias", skill_id=skill.id)
        sessions.add(alias2)
        with pytest.raises(IntegrityError):
            sessions.commit()
    finally:
        sessions.rollback()
        sessions.query(SkillAliases).filter(SkillAliases.alias == "Test Alias").delete()
        sessions.query(Skill).filter(Skill.name == "Test Skill for Alias").delete()
        sessions.commit()
        sessions.close()