from app.services.skill_normalizer import find_skill, normalize_text
import pytest
from app.services.skill_service import create_skill


def test_create_skill_makes_skill_findable_by_its_own_name(db_session):
    created = create_skill(db_session, "Test Skill X")
    found = find_skill(db_session, "Test Skill X")

    assert found is not None
    assert found.id == created.id


def test_create_skill_duplicate_raises_value_error(db_session):
    create_skill(db_session, "Test Skill Y")
    with pytest.raises(ValueError):
        create_skill(db_session, "   test SKILL y   ")
