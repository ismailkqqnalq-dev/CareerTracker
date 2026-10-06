import pytest
from app.services.skill_normalizer import normalize_text
@pytest.mark.parametrize("input_text,expected", [
    ("  Python  ", "python"),
    ("JavaScript", "javascript"),
    ("  C++  ", "c++"),
    ("POSTGRESQL", "postgresql"),
    ("nODE.JS", "node.js"),
    ("machine Learning", "machine learning"),
    ("", ""),
    (" ", "")
])
def test_normalize_text(input_text, expected):    
    assert normalize_text(input_text) == expected