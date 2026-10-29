"""Conservative, rule-based extraction from job-description text."""

import re

from sqlalchemy.orm import Session

from app.models.skills import (
    PersonalSkillAlias,
    Skill,
    SkillAliases,
    SkillSuggestion,
)
from app.services.skill_access import visible_skills
from app.services.skill_normalizer import normalize_text


_ROLE_LABEL = re.compile(
    r"^\s*(?:position|job title|role|title|pozisyon|rol|unvan)\s*[:：-]\s*(.*?)\s*$",
    re.IGNORECASE,
)
_REQUIRED_HEADING = re.compile(
    r"^\s*(?:required(?:\s+(?:skills?|qualifications?))?|requirements?|"
    r"what you(?:'|’)ll need|must[- ]have|aranan nitelikler|"
    r"is icin gerekli beceriler|"
    r"gereklilikler|zorunlu (?:beceriler|nitelikler))\s*[:：]?\s*$",
    re.IGNORECASE,
)
_PREFERRED_HEADING = re.compile(
    r"^\s*(?:preferred(?:\s+(?:skills?|qualifications?))?|nice to have|"
    r"bonus points|tercihen|tercih sebebi|tercih edilen(?: beceriler)?|"
    r"one cikan ozellikler|"
    r"avantaj)\s*[:：]?\s*$",
    re.IGNORECASE,
)
_SHORT_AMBIGUOUS_ALIASES = {"c", "r", "go"}
_SHORT_ALIAS_CONTEXT = re.compile(
    r"\b(?:programming|programming language|language|experience|"
    r"dili|programlama|deneyim|tecrube|beceri)\b",
    re.IGNORECASE,
)
_MATCH_FOLD_TRANSLATION = str.maketrans(
    {
        "ş": "s", "Ş": "s",
        "ğ": "g", "Ğ": "g",
        "ç": "c", "Ç": "c",
        "ö": "o", "Ö": "o",
        "ü": "u", "Ü": "u",
        "ı": "i", "İ": "i",
        "â": "a", "Â": "a",
        "î": "i", "Î": "i",
        "û": "u", "Û": "u",
    }
)


def _fold_for_matching(value: str) -> str:
    """Fold supported Turkish/OCR variants one character at a time."""
    # Translate dotted capital İ before lower(): its default lower() expands to
    # two code points, which would invalidate offsets into the original line.
    return value.translate(_MATCH_FOLD_TRANSLATION).lower()


def _visible_aliases(db: Session, user_id: int) -> dict[str, int]:
    visible = visible_skills(db, user_id).all()
    visible_ids = {skill.id for skill in visible}
    aliases: dict[str, int] = {}

    # Keep the same personal-over-shared precedence used by find_skill().
    for suggestion in (
        db.query(SkillSuggestion)
        .filter(
            SkillSuggestion.user_id == user_id,
            SkillSuggestion.status == "accepted",
            SkillSuggestion.resolved_skill_id.is_not(None),
        )
        .order_by(SkillSuggestion.id)
        .all()
    ):
        if suggestion.resolved_skill_id in visible_ids:
            aliases.setdefault(
                normalize_text(suggestion.normalized_name),
                suggestion.resolved_skill_id,
            )

    for alias in (
        db.query(PersonalSkillAlias)
        .filter(PersonalSkillAlias.user_id == user_id)
        .order_by(PersonalSkillAlias.id)
        .all()
    ):
        if alias.skill_id in visible_ids:
            aliases.setdefault(normalize_text(alias.alias), alias.skill_id)

    for alias in db.query(SkillAliases).order_by(SkillAliases.id).all():
        if alias.skill_id in visible_ids:
            aliases.setdefault(normalize_text(alias.alias), alias.skill_id)

    # Canonical names cover older catalog rows that predate self-alias seeding.
    for skill in visible:
        aliases.setdefault(normalize_text(skill.name), skill.id)
    return aliases


def _line_section(line: str, current: str) -> tuple[str, bool]:
    folded_line = _fold_for_matching(line)
    if _REQUIRED_HEADING.fullmatch(folded_line):
        return "required", True
    if _PREFERRED_HEADING.fullmatch(folded_line):
        return "preferred", True
    if len(line) < 80 and line.endswith(":"):
        return "unspecified", True
    return current, False


def analyze_job_text(db: Session, *, user_id: int, text: str) -> dict:
    """Return explicit skill mentions; never writes or guesses missing catalog terms."""
    aliases = _visible_aliases(db, user_id)
    visible = {skill.id: skill for skill in visible_skills(db, user_id).all()}
    folded_alias_owners: dict[str, set[int]] = {}
    for alias, skill_id in aliases.items():
        folded_alias = _fold_for_matching(alias)
        if folded_alias:
            folded_alias_owners.setdefault(folded_alias, set()).add(skill_id)

    # Folding may merge previously distinct spellings. Never assign an
    # ambiguous folded spelling to whichever skill happened to be visited first.
    patterns = [
        (
            alias,
            next(iter(skill_ids)) if len(skill_ids) == 1 else None,
            re.compile(r"(?<!\w)" + re.escape(alias) + r"(?!\w)"),
        )
        for alias, skill_ids in sorted(
            folded_alias_owners.items(),
            key=lambda item: (-len(item[0]), item[0]),
        )
    ]

    role = None
    section = "unspecified"
    extracted: dict[int, dict] = {}

    for line_number, line in enumerate(text.splitlines(), start=1):
        role_match = _ROLE_LABEL.match(line)
        if role is None and role_match and role_match.group(1):
            role = role_match.group(1).strip()

        section, is_heading = _line_section(line, section)
        if is_heading:
            continue

        folded_line = _fold_for_matching(line)
        line_matches = []
        for alias, skill_id, pattern in patterns:
            if skill_id is not None and skill_id not in visible:
                continue
            for match in pattern.finditer(folded_line):
                if alias in _SHORT_AMBIGUOUS_ALIASES:
                    context = line[max(0, match.start() - 16):match.end() + 16]
                    if not _SHORT_ALIAS_CONTEXT.search(_fold_for_matching(context)):
                        continue
                line_matches.append((match, alias, skill_id))

        # Prefer the longest catalog phrase when aliases overlap (for example,
        # a skill named "C" must not also match the "C" in "C#" or "C++").
        accepted_matches = []
        for match, alias, skill_id in sorted(
            line_matches,
            key=lambda item: (-(item[0].end() - item[0].start()), item[0].start()),
        ):
            if any(
                match.start() < accepted.end() and accepted.start() < match.end()
                for accepted, _, _ in accepted_matches
            ):
                continue
            accepted_matches.append((match, alias, skill_id))

        for match, _alias, skill_id in accepted_matches:
            if skill_id is None:
                # An ambiguous longer folded phrase blocks shorter overlaps,
                # but is never attributed to either skill.
                continue
            skill = visible[skill_id]
            entry = extracted.setdefault(
                skill_id,
                {
                    "skill_id": skill.id,
                    "name": skill.name,
                    "category": skill.category,
                    "occurrences": [],
                    "_seen": set(),
                },
            )
            key = (line_number, match.start(), match.end())
            if key in entry["_seen"]:
                continue
            entry["_seen"].add(key)
            entry["occurrences"].append(
                {
                    "line_number": line_number,
                    "matched_text": line[match.start():match.end()],
                    "section": section,
                }
            )

    results = []
    for skill_id in sorted(extracted, key=lambda item: visible[item].name.casefold()):
        entry = extracted[skill_id]
        entry.pop("_seen")
        results.append(entry)
    return {"role": role, "skills": results}
