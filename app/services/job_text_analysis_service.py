"""Conservative, rule-based extraction from job-description text."""

import re
import unicodedata

from sqlalchemy.orm import Session

from app.models.skills import (
    PersonalSkillAlias,
    Skill,
    SkillAliases,
    SkillSuggestion,
)
from app.services.skill_access import visible_skills
from app.services.skill_normalizer import normalize_text


MAX_METADATA_LINE_LENGTH = 200
_ROLE_LABEL = re.compile(
    r"(?:position|job title|role|title|pozisyon|rol|unvan)[ \t]*[:\uff1a-][ \t]*(?P<value>.+)",
    re.IGNORECASE,
)
_REQUIRED_HEADING = re.compile(
    r"(?:required(?:[ \t]+(?:skills?|qualifications?))?|requirements?|"
    r"what you(?:'|\u2019)ll need|must[- ]have|aranan[ \t]+nitelikler|"
    r"is icin gerekli beceriler|"
    r"gereklilikler|zorunlu[ \t]+(?:beceriler|nitelikler))[ \t]*[:\uff1a]?",
    re.IGNORECASE,
)
_PREFERRED_HEADING = re.compile(
    r"(?:preferred(?:[ \t]+(?:skills?|qualifications?))?|nice to have|"
    r"bonus points|tercihen|tercih sebebi|tercih edilen(?: beceriler)?|"
    r"one cikan ozellikler|avantaj)[ \t]*[:\uff1a]?",
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
    """Canonicalize Unicode, then fold supported Turkish/OCR variants."""
    # Translate dotted capital İ before lower(): its default lower() expands to
    # two code points, which would invalidate offsets into the original line.
    return unicodedata.normalize("NFC", value).translate(_MATCH_FOLD_TRANSLATION).lower()


def _hangul_jamo_type(char: str) -> str | None:
    codepoint = ord(char)
    if 0x1100 <= codepoint <= 0x115F or 0xA960 <= codepoint <= 0xA97C:
        return "L"
    if 0x1160 <= codepoint <= 0x11A7 or 0xD7B0 <= codepoint <= 0xD7C6:
        return "V"
    if 0x11A8 <= codepoint <= 0x11FF or 0xD7CB <= codepoint <= 0xD7FB:
        return "T"
    if 0xAC00 <= codepoint <= 0xD7A3 and (codepoint - 0xAC00) % 28 == 0:
        return "LV"
    return None


def _fold_for_matching_with_offsets(
    value: str,
) -> tuple[str, list[tuple[int, int]] | None]:
    """Return the folded form plus source spans for each folded code point."""
    normalized_value = unicodedata.normalize("NFC", value)
    folded_value = _fold_for_matching(normalized_value)
    if normalized_value == value and len(folded_value) == len(value):
        # Most input lines are already NFC and the supported Turkish folding is
        # one-to-one, so keep the hot path offset-free.
        return folded_value, None

    folded_parts = []
    source_spans: list[tuple[int, int]] = []
    cluster_start = 0

    def append_cluster(start: int, end: int) -> None:
        source_cluster = value[start:end]
        folded_cluster = _fold_for_matching(source_cluster)
        folded_parts.append(folded_cluster)
        source_spans.extend([(start, end)] * len(folded_cluster))

    for index, char in enumerate(value):
        if index == cluster_start:
            continue
        is_mark = unicodedata.combining(char) != 0 or unicodedata.category(char).startswith("M")
        if is_mark:
            continue

        normalized_cluster = unicodedata.normalize("NFC", value[cluster_start:index])
        previous_hangul_type = _hangul_jamo_type(normalized_cluster[-1])
        current_hangul_type = _hangul_jamo_type(char)
        joins_hangul = (
            previous_hangul_type == "L" and current_hangul_type == "V"
        ) or (
            previous_hangul_type == "LV" and current_hangul_type == "T"
        )
        if joins_hangul:
            continue

        append_cluster(cluster_start, index)
        cluster_start = index

    if cluster_start < len(value):
        append_cluster(cluster_start, len(value))

    return "".join(folded_parts), source_spans


def _source_span(
    source_spans: list[tuple[int, int]] | None,
    start: int,
    end: int,
) -> tuple[int, int]:
    if source_spans is None:
        return start, end
    return source_spans[start][0], source_spans[end - 1][1]


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
    clean_line = line.strip()
    if len(clean_line) > MAX_METADATA_LINE_LENGTH:
        return current, False

    folded_line = _fold_for_matching(clean_line)
    if _REQUIRED_HEADING.fullmatch(folded_line):
        return "required", True
    if _PREFERRED_HEADING.fullmatch(folded_line):
        return "preferred", True
    if len(clean_line) < 80 and clean_line.endswith(":"):
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
        clean_line = line.strip()
        metadata_line = len(clean_line) <= MAX_METADATA_LINE_LENGTH
        if metadata_line:
            role_match = _ROLE_LABEL.fullmatch(clean_line)
            if role is None and role_match and role_match.group("value").strip():
                role = role_match.group("value").strip()
            section, is_heading = _line_section(clean_line, section)
        else:
            is_heading = False

        if is_heading:
            continue

        folded_line, source_spans = _fold_for_matching_with_offsets(line)
        line_matches = []
        for alias, skill_id, pattern in patterns:
            if skill_id is not None and skill_id not in visible:
                continue
            for match in pattern.finditer(folded_line):
                if alias in _SHORT_AMBIGUOUS_ALIASES:
                    source_start, source_end = _source_span(
                        source_spans, match.start(), match.end()
                    )
                    context = line[max(0, source_start - 16):source_end + 16]
                    if not _SHORT_ALIAS_CONTEXT.search(_fold_for_matching(context)):
                        continue
                else:
                    source_start, source_end = _source_span(
                        source_spans, match.start(), match.end()
                    )
                line_matches.append((match, alias, skill_id, source_start, source_end))

        # Prefer the longest catalog phrase when aliases overlap (for example,
        # a skill named "C" must not also match the "C" in "C#" or "C++").
        accepted_matches = []
        for match, alias, skill_id, source_start, source_end in sorted(
            line_matches,
            key=lambda item: (-(item[0].end() - item[0].start()), item[0].start()),
        ):
            if any(
                source_start < accepted[4] and accepted[3] < source_end
                for accepted in accepted_matches
            ):
                continue
            accepted_matches.append((match, alias, skill_id, source_start, source_end))

        for match, _alias, skill_id, source_start, source_end in accepted_matches:
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
            key = (line_number, source_start, source_end)
            if key in entry["_seen"]:
                continue
            entry["_seen"].add(key)
            entry["occurrences"].append(
                {
                    "line_number": line_number,
                    "matched_text": line[source_start:source_end],
                    "section": section,
                }
            )

    results = []
    for skill_id in sorted(extracted, key=lambda item: visible[item].name.casefold()):
        entry = extracted[skill_id]
        entry.pop("_seen")
        results.append(entry)
    return {"role": role, "skills": results}
