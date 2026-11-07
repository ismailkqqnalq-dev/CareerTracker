"""Conservative, rule-based extraction from job-description text."""

import re
import unicodedata
from functools import lru_cache

from sqlalchemy.orm import Session

from app.models.skills import (
    PersonalSkillAlias,
    Skill,
    SkillAliases,
    SkillSuggestion,
    UserSkill,
)
from app.services.skill_access import visible_skills
from app.services.skill_normalizer import normalize_text


MAX_METADATA_LINE_LENGTH = 200
MAX_HEADLINE_ROLE_LENGTH = 140
_METADATA_LABELS = {
    "position": "role",
    "job title": "role",
    "title": "role",
    "role": "role",
    "position name": "role",
    "pozisyon": "role",
    "pozisyon adi": "role",
    "rol": "role",
    "unvan": "role",
    "is unvani": "role",
    "company": "company",
    "company name": "company",
    "employer": "company",
    "sirket": "company",
    "sirket adi": "company",
    "isveren": "company",
    "location": "location",
    "city": "location",
    "konum": "location",
    "lokasyon": "location",
    "sehir": "location",
    "employment type": "employment_type",
    "job type": "employment_type",
    "position type": "employment_type",
    "employment": "employment_type",
    "istihdam turu": "employment_type",
    "calisma turu": "employment_type",
    "is turu": "employment_type",
    "work arrangement": "work_arrangement",
    "work model": "work_arrangement",
    "workplace type": "work_arrangement",
    "location type": "work_arrangement",
    "calisma modeli": "work_arrangement",
    "calisma bicimi": "work_arrangement",
    "calisma sekli": "work_arrangement",
    "salary": "salary",
    "salary range": "salary",
    "compensation": "salary",
    "pay range": "salary",
    "maas": "salary",
    "maas araligi": "salary",
    "ucret": "salary",
    "ucret araligi": "salary",
    "experience": "experience",
    "years of experience": "experience",
    "work experience": "experience",
    "required experience": "experience",
    "deneyim": "experience",
    "deneyim suresi": "experience",
    "tecrube": "experience",
    "education": "education",
    "education level": "education",
    "degree": "education",
    "egitim": "education",
    "egitim duzeyi": "education",
    "ogrenim": "education",
    "mezuniyet": "education",
    "application url": "application_url",
    "application link": "application_url",
    "apply url": "application_url",
    "apply link": "application_url",
    "basvuru url": "application_url",
    "basvuru linki": "application_url",
    "basvuru baglantisi": "application_url",
}
_REQUIRED_HEADING = re.compile(
    r"(?:required(?:[ \t]+(?:skills?|qualifications?))?|requirements?|"
    r"expected[ \t]+(?:skills?|qualifications?|experience)|"
    r"(?:minimum|basic)[ \t]+(?:requirements?|qualifications?)|qualifications?|"
    r"essential[ \t]+(?:skills?|qualifications?)|skills?[ \t]+required|"
    r"about[ \t]+you|"
    r"we(?:'|\u2019)re excited about you because you have(?:\.{3}|\u2026)|"
    r"who[ \t]+we[ \t]+are[ \t]+looking[ \t]+for|"
    r"what you will need(?:[ \t]+to[ \t]+(?:succeed|be[ \t]+successful))?|"
    r"what you(?:'|\u2019)ll[ \t]+(?:"
    r"need(?:[ \t]+to[ \t]+(?:succeed|be[ \t]+successful))?|bring)|"
    r"to[ \t]+be[ \t]+successful,[ \t]+you(?:'|\u2019)ll[ \t]+need|"
    r"the[ \t]+essentials|"
    r"what you[ \t]+bring|"
    r"what we(?:'|\u2019)re[ \t]+looking for|must[- ]have|"
    r"aranan[ \t]+(?:nitelikler|ozellikler|yetkinlikler)|"
    r"istenen[ \t]+(?:nitelikler|ozellikler|yetkinlikler)|"
    r"temel[ \t]+(?:nitelikler|yetkinlikler)|"
    r"gerekli[ \t]+(?:nitelikler|ozellikler|yetkinlikler)|"
    r"adaydan beklentiler|"
    r"is icin gerekli beceriler|"
    r"gereklilikler|zorunlu[ \t]+(?:beceriler|nitelikler))[ \t]*[:\uff1a]?",
    re.IGNORECASE,
)
_PREFERRED_HEADING = re.compile(
    r"(?:preferred(?:[ \t]+(?:skills?|qualifications?|experience))?|"
    r"ideally,[ \t]+you[ \t]+also|ideally[ \t]+also|"
    r"desired[ \t]+(?:skills?|qualifications?|experience)|"
    r"desirable[ \t]+(?:skills?|qualifications?|experience)|"
    r"nice[- ]to[- ]haves?(?:,?[ \t]+but[ \t]+not[ \t]+required)?|"
    r"good[ \t]+to[ \t]+have|a[ \t]+plus|"
    r"bonus(?: points)?(?: if you have| for)?|"
    r"any of the following (?:would be|is) a bonus[.!]?|"
    r"tercihen|tercih sebebi|"
    r"tercih edilen(?:[ \t]+(?:beceriler|nitelikler|yetkinlikler))?|"
    r"arti sayilan[ \t]+(?:ozellikler|yetkinlikler|beceriler)|"
    r"one cikan ozellikler|avantaj)[ \t]*[:\uff1a]?",
    re.IGNORECASE,
)
_SHORT_AMBIGUOUS_ALIASES = {"c", "r", "go"}
_SHORT_ALIAS_CONTEXT = re.compile(
    r"\b(?:programming|programming language|language|experience|"
    r"dili|programlama|deneyim|tecrube|beceri)\b",
    re.IGNORECASE,
)
_CONTEXTUAL_ALIAS_CONTEXT = {
    "yolo": re.compile(
        r"\b(?:computer[ -]+vision|object[ -]+detection|"
        r"detection[ -]+networks?|image[ -]+classification|"
        r"vision[ -]+models?)\b",
        re.IGNORECASE,
    ),
    "feast": re.compile(
        r"\b(?:feature[ -]+stores?|feature[ -]+store[ -]+platform)\b",
        re.IGNORECASE,
    ),
    "step functions": re.compile(
        r"\b(?:aws|amazon|lambda|glue|athena|emr)\b",
        re.IGNORECASE,
    ),
    "spark": re.compile(
        r"\b(?:apache|pyspark|spark[ -]+sql|python|java|scala|sql|"
        r"programming[ -]+languages?|lakehouse|data[ -]+(?:lake|processing)|"
        r"distributed[ -]+(?:computing|processing)|big[ -]+data)\b",
        re.IGNORECASE,
    ),
    "iceberg": re.compile(
        r"\b(?:apache|lakehouse|data[ -]+lake|table[ -]+format|"
        r"iceberg[ -]+tables?|open[ -]+table[ -]+formats?)\b",
        re.IGNORECASE,
    ),
    "airflow": re.compile(
        r"\b(?:apache|workflow|orchestrat\w*|pipeline\w*|mwaa|dag)\b",
        re.IGNORECASE,
    ),
    "redshift": re.compile(
        r"\b(?:aws|amazon|data[ -]+warehouse|analytic(?:al|s?)[ -]+database|"
        r"warehouse|snowflake|s3|redshift[ -]+cluster|olap)\b",
        re.IGNORECASE,
    ),
    "modal": re.compile(
        r"\b(?:machine[ -]+learning|ml|model[ -]+serving|inference|gpu|"
        r"training|pytorch|tensorflow|llm)\b",
        re.IGNORECASE,
    ),
    "bert": re.compile(
        r"\b(?:transformers?|nlp|language[ -]+models?|llm|text[ -]+models?|"
        r"hugging[ -]+face)\b",
        re.IGNORECASE,
    ),
    "bart": re.compile(
        r"\b(?:transformers?|nlp|language[ -]+models?|llm|text[ -]+models?|"
        r"hugging[ -]+face)\b",
        re.IGNORECASE,
    ),
    "jax": re.compile(
        r"\b(?:machine[ -]+learning|ml|nlp|framework|deep[ -]+learning|"
        r"pytorch|tensorflow|transformers?|hugging[ -]+face|bert|bart|"
        r"gradients?|autodiff|numerical[ -]+computing)\b",
        re.IGNORECASE,
    ),
    "embeddings": re.compile(
        r"\b(?:vector|semantic|search|retrieval|machine[ -]+learning|ml|llm|nlp)\b",
        re.IGNORECASE,
    ),
    "braintrust": re.compile(
        r"\b(?:llm|machine[ -]+learning|ml|evaluation|eval\w*|benchmark\w*|"
        r"observability|prompt\w*)\b",
        re.IGNORECASE,
    ),
    "reranking": re.compile(
        r"\b(?:search|retrieval|ranking|relevance|cross[ -]+encoder|query)\b",
        re.IGNORECASE,
    ),
    "spelling correction": re.compile(
        r"\b(?:search|query|nlp|text|language[ -]+model)\b",
        re.IGNORECASE,
    ),
}
_ABOUT_ORGANIZATION_HEADING = re.compile(
    r"About[ \t]+(?:(?:the|our)[ \t]+)?[A-Z][\w&'-]*"
    r"(?:[ \t]+(?:[A-Z][\w&'-]*|and|of|the)){0,3}[ \t]*[:\uff1a]?"
)
_NEUTRAL_HEADING = re.compile(
    r"(?:about(?:[ \t]+(?:us|the company|our company|the role|this role|our team|the team))?|"
    r"location[ \t]+requirement|"
    r"(?:the[ \t]+)?role(?:[ \t]+overview)?|"
    r"(?:position|job)[ \t]+overview|"
    r"(?:your[ \t]+|(?:key[ \t]+|job[ \t]+)?)responsibilities|"
    r"you(?:'|\u2019)re excited about this opportunity because you will(?:\.{3}|\u2026)|"
    r"what you(?:'|\u2019)ll do|what you will do|"
    r"some things you might work on|"
    r"(?:our[ \t]+)?(?:tech|technical)[ \t]+stack|"
    r"technical environment|technologies[ \t]+we[ \t]+love|"
    r"(?:the[ \t]+)?(?:rewards package|benefits)|"
    r"why join us|what we offer)[ \t]*[:\uff1a]?",
    re.IGNORECASE,
)
_HEADLINE_ROLE_SUFFIX = re.compile(
    r"\b(?:engineers?|developers?|scientists?|analysts?|architects?|designers?|"
    r"managers?|consultants?|specialists?|administrators?|technicians?|"
    r"programmers?|testers?|interns?|researchers?|product owners?|"
    r"scrum masters?|directors?|leads?)\b"
    r"(?:[ \t]*\([^()\r\n]{1,80}\))?"
    r"(?:[ \t]*[-\u2013\u2014|][ \t]+[\w+#./]+"
    r"(?:[ \t]+[\w+#./]+){0,2})?$",
    re.IGNORECASE,
)
_HEADLINE_SENTENCE_START = re.compile(
    r"^(?:we|you|our|join|about|looking for|we are|we're|we\u2019re)\b",
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


_WORD_CHARACTER = re.compile(r"\w")


@lru_cache(maxsize=16)
def _build_alias_automaton(
    aliases: tuple[tuple[str, int | None], ...],
) -> tuple[list[dict[str, int]], list[int], list[list[tuple[str, int | None]]]]:
    """Build a trie with failure links so each line is scanned once."""
    transitions: list[dict[str, int]] = [{}]
    failures = [0]
    outputs: list[list[tuple[str, int | None]]] = [[]]

    for alias, skill_id in aliases:
        state = 0
        for character in alias:
            next_state = transitions[state].get(character)
            if next_state is None:
                next_state = len(transitions)
                transitions[state][character] = next_state
                transitions.append({})
                failures.append(0)
                outputs.append([])
            state = next_state
        outputs[state].append((alias, skill_id))

    queue = list(transitions[0].values())
    queue_index = 0
    while queue_index < len(queue):
        state = queue[queue_index]
        queue_index += 1
        for character, next_state in transitions[state].items():
            fallback = failures[state]
            while fallback and character not in transitions[fallback]:
                fallback = failures[fallback]
            failures[next_state] = transitions[fallback].get(character, 0)
            outputs[next_state].extend(outputs[failures[next_state]])
            queue.append(next_state)

    return transitions, failures, outputs


def _find_alias_matches(
    text: str,
    automaton: tuple[
        list[dict[str, int]],
        list[int],
        list[list[tuple[str, int | None]]],
    ],
) -> list[tuple[int, int, str, int | None]]:
    """Find Unicode word-bounded aliases in one pass, preserving finditer semantics."""
    transitions, failures, outputs = automaton
    state = 0
    next_start_by_alias: dict[str, int] = {}
    matches = []

    for index, character in enumerate(text):
        while state and character not in transitions[state]:
            state = failures[state]
        state = transitions[state].get(character, 0)
        end = index + 1
        for alias, skill_id in outputs[state]:
            start = end - len(alias)
            if start < next_start_by_alias.get(alias, 0):
                continue
            if start and _WORD_CHARACTER.fullmatch(text[start - 1]):
                continue
            if end < len(text) and _WORD_CHARACTER.fullmatch(text[end]):
                continue
            next_start_by_alias[alias] = end
            matches.append((start, end, alias, skill_id))

    return matches


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
    if _ABOUT_ORGANIZATION_HEADING.fullmatch(clean_line):
        return "unspecified", True
    if _NEUTRAL_HEADING.fullmatch(folded_line):
        return "unspecified", True
    if len(clean_line) < 80 and clean_line.endswith(":"):
        return "unspecified", True
    return current, False


def _parse_metadata_line(line: str) -> tuple[str, str] | None:
    """Read only short, explicitly labeled metadata lines; never infer values."""
    clean_line = line.strip()
    if not clean_line or len(clean_line) > MAX_METADATA_LINE_LENGTH:
        return None

    separator_indices = [
        index
        for separator in (":", "：")
        if (index := clean_line.find(separator)) >= 0
    ]
    separator_index = min(separator_indices, default=-1)
    dash_separated = separator_index < 0
    if dash_separated:
        separator_index = clean_line.find("-")
    if separator_index < 0:
        return None

    label = _fold_for_matching(clean_line[:separator_index].strip())
    field_name = _METADATA_LABELS.get(label)
    value = clean_line[separator_index + 1 :].strip()
    if field_name is None or not value or (dash_separated and field_name != "role"):
        return None
    return field_name, value


def _parse_headline_role(line: str) -> str | None:
    """Accept a short title-like headline, never infer a role from prose."""
    clean_line = line.strip()
    if (
        not clean_line
        or len(clean_line) > MAX_HEADLINE_ROLE_LENGTH
        or any(char in clean_line for char in ":：!?\n\r")
        or clean_line.endswith((".", ";"))
        or _HEADLINE_SENTENCE_START.search(_fold_for_matching(clean_line))
    ):
        return None
    return clean_line if _HEADLINE_ROLE_SUFFIX.search(clean_line) else None


def _section_profile_match(
    skill_ids: set[int],
    extracted: dict[int, dict],
    profile: dict[int, UserSkill],
) -> dict:
    matched_ids = skill_ids.intersection(profile)
    missing_ids = skill_ids.difference(profile)
    total_count = len(skill_ids)
    return {
        "total_count": total_count,
        "matched_count": len(matched_ids),
        "match_percentage": (
            round(len(matched_ids) / total_count * 100, 2)
            if total_count
            else None
        ),
        "missing_skills": sorted(
            extracted[skill_id]["name"] for skill_id in missing_ids
        ),
    }


def analyze_job_text(db: Session, *, user_id: int, text: str) -> dict:
    """Extract explicit labels and skill mentions; compare them to this user's profile."""
    aliases = _visible_aliases(db, user_id)
    visible = {skill.id: skill for skill in visible_skills(db, user_id).all()}
    folded_alias_owners: dict[str, set[int]] = {}
    for alias, skill_id in aliases.items():
        folded_alias = _fold_for_matching(alias)
        if folded_alias:
            folded_alias_owners.setdefault(folded_alias, set()).add(skill_id)

    # Folding may merge previously distinct spellings. Never assign an
    # ambiguous folded spelling to whichever skill happened to be visited first.
    alias_patterns = tuple(
        (alias, next(iter(skill_ids)) if len(skill_ids) == 1 else None)
        for alias, skill_ids in sorted(
            folded_alias_owners.items(),
            key=lambda item: (-len(item[0]), item[0]),
        )
    )
    alias_automaton = _build_alias_automaton(alias_patterns)

    role = None
    role_line_number = None
    role_source = None
    metadata = {
        "company": None,
        "location": None,
        "employment_type": None,
        "work_arrangement": None,
        "salary": None,
        "experience": None,
        "education": None,
        "application_url": None,
    }
    section = "unspecified"
    extracted: dict[int, dict] = {}
    headline_role = None
    headline_role_line_number = None

    for line_number, line in enumerate(text.splitlines(), start=1):
        clean_line = line.strip()
        if line_number <= 5 and headline_role is None:
            headline_role = _parse_headline_role(clean_line)
            if headline_role is not None:
                headline_role_line_number = line_number
        metadata_line = len(clean_line) <= MAX_METADATA_LINE_LENGTH
        if metadata_line:
            parsed_field = _parse_metadata_line(clean_line)
            if parsed_field:
                field_name, value = parsed_field
                if field_name == "role" and role is None:
                    role = value
                    role_line_number = line_number
                    role_source = "explicit"
                elif field_name != "role" and metadata[field_name] is None:
                    metadata[field_name] = {
                        "value": value,
                        "line_number": line_number,
                    }
            section, is_heading = _line_section(clean_line, section)
        else:
            is_heading = False

        if is_heading:
            continue

        folded_line, source_spans = _fold_for_matching_with_offsets(line)
        line_matches = []
        for match_start, match_end, alias, skill_id in _find_alias_matches(
            folded_line, alias_automaton
        ):
            if skill_id is not None and skill_id not in visible:
                continue
            source_start, source_end = _source_span(
                source_spans, match_start, match_end
            )
            if alias in _CONTEXTUAL_ALIAS_CONTEXT:
                context = line[
                    max(0, source_start - 80):min(len(line), source_end + 80)
                ]
                if not _CONTEXTUAL_ALIAS_CONTEXT[alias].search(
                    _fold_for_matching(context)
                ):
                    continue
            elif alias in _SHORT_AMBIGUOUS_ALIASES:
                context = line[max(0, source_start - 16):source_end + 16]
                if not _SHORT_ALIAS_CONTEXT.search(_fold_for_matching(context)):
                    continue
            line_matches.append(
                (match_start, match_end, alias, skill_id, source_start, source_end)
            )

        # Prefer the longest catalog phrase when aliases overlap (for example,
        # a skill named "C" must not also match the "C" in "C#" or "C++").
        accepted_matches = []
        for match_start, match_end, alias, skill_id, source_start, source_end in sorted(
            line_matches,
            key=lambda item: (-(item[1] - item[0]), item[0]),
        ):
            if any(
                source_start < accepted[5] and accepted[4] < source_end
                for accepted in accepted_matches
            ):
                continue
            accepted_matches.append(
                (match_start, match_end, alias, skill_id, source_start, source_end)
            )

        for (
            _match_start,
            _match_end,
            _alias,
            skill_id,
            source_start,
            source_end,
        ) in accepted_matches:
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

    if role is None and headline_role is not None:
        role = headline_role
        role_line_number = headline_role_line_number
        role_source = "headline"

    profile = {
        user_skill.skill_id: user_skill
        for user_skill in db.query(UserSkill)
        .filter(UserSkill.user_id == user_id)
        .all()
    }
    section_skill_ids = {
        "required": set(),
        "preferred": set(),
        "unspecified": set(),
    }
    for skill_id, entry in extracted.items():
        user_skill = profile.get(skill_id)
        entry["profile_status"] = "in_profile" if user_skill else "missing"
        entry["profile_proficiency_level"] = (
            user_skill.proficiency_level if user_skill else None
        )
        entry["profile_years_experience"] = (
            user_skill.years_experience if user_skill else None
        )
        for occurrence in entry["occurrences"]:
            section_skill_ids[occurrence["section"]].add(skill_id)

    results = []
    for skill_id in sorted(extracted, key=lambda item: visible[item].name.casefold()):
        entry = extracted[skill_id]
        entry.pop("_seen")
        results.append(entry)

    return {
        "role": role,
        "role_line_number": role_line_number,
        "role_source": role_source,
        "metadata": metadata,
        "skills": results,
        "profile_match": {
            section_name: _section_profile_match(
                skill_ids,
                extracted,
                profile,
            )
            for section_name, skill_ids in section_skill_ids.items()
        },
    }
