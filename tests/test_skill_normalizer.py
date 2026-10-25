import pytest
from app.services.skill_normalizer import normalize_text, find_skill
from app.models.skills import Skill, SkillAliases

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

def test_find_skill(db_session):
    skill = Skill(name="Test PostgreSQL")
    db_session.add(skill)
    db_session.commit()
    db_session.add(SkillAliases(alias="test postgresql", skill_id=skill.id))
    db_session.commit()

    found = find_skill(db_session, " TEST PostgreSQL ")

    assert found is not None
    assert found.name == "Test PostgreSQL"

def test_find_skill_returns_none_for_unknown_text(db_session):
    assert find_skill(db_session, "zzzzz-Unknown Skill-zzzzz") is None
