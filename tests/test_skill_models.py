from app.models.skills import Skill
from app.models.skills import SkillAliases

import pytest
from sqlalchemy.exc import IntegrityError

def test_duplicate_skill_name_raises_integrity_error(db_session):
    db_session.add(Skill(name="Test Skill"))
    db_session.commit()
    db_session.add(Skill(name="Test Skill"))
    with pytest.raises(IntegrityError):
        db_session.commit()

def test_duplicate_skill_alias_raises_integrity_error(db_session):
    skill = Skill(name="Test Skill for Alias")
    db_session.add(skill)
    db_session.commit()
    db_session.add(SkillAliases(alias="Test Alias", skill_id=skill.id))
    db_session.commit()
    db_session.add(SkillAliases(alias="Test Alias", skill_id=skill.id))
    with pytest.raises(IntegrityError):
        db_session.commit()
