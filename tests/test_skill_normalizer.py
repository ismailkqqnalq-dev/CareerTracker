import pytest
from app.services.skill_normalizer import normalize_text, find_skill
from app.models.skills import Skill, SkillAliases
from app.database import session

@pytest.mark.parametrize("input_text,expected", [
    ("  Python  ", "python"),
    ("JavaScript", "javascript"),
    ("  C++  ", "c++"),
    ("POSTGRESQL", "postgresql"),
    ("nODE.JS", "node.js"),
    ("machine          Learning", "machine learning"),
    ("", ""),
    (" ", ""),
    ("Fastapı", "fastapi"),
    ("FASTAPİ", "fastapi")
])
def test_normalize_text(input_text, expected):    
    assert normalize_text(input_text) == expected

def test_find_skill():
    sessions = session.SessionLocal()
    try:
        
        skill = Skill(name="Test PostgreSQL")
        sessions.add(skill)
        sessions.commit()
        sessions.add(SkillAliases(alias="test postgresql", skill_id=skill.id))
        sessions.commit()
        session_skill = find_skill(sessions, " TEST PostgreSQL ")
        assert session_skill is not None
        assert session_skill.name == "Test PostgreSQL"
    finally:
        sessions.rollback()
        sessions.query(SkillAliases).filter(SkillAliases.alias == "test postgresql").delete()
        sessions.query(Skill).filter(Skill.name == "Test PostgreSQL").delete()
        sessions.commit()
        sessions.close()

def test_find_skill_returns_none_for_unknown_text():
    sessions = session.SessionLocal()
    try:
        found_skill = find_skill(sessions, "zzzzz-Unknown Skill-zzzzz")
        assert found_skill is None
    finally:
        sessions.close()