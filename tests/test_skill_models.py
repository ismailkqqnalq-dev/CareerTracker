from app.models.skills import Skill
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