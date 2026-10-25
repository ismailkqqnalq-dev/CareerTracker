import re
from difflib import SequenceMatcher

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.skills import Skill, SkillAliases, SkillSuggestion, PersonalSkillAlias
from app.services.skill_access import get_visible_skill, visible_skills
from app.services.skill_normalizer import find_skill, normalize_text


_CANDIDATE_TEXT_ALIASES = {
    "c#": "csharp",
    "c sharp": "csharp",
    "c-sharp": "csharp",
    "csharp": "csharp",
    "c++": "cpp",
    "c plus plus": "cpp",
    "cplusplus": "cpp",
    "cpp": "cpp",
}


def submit_suggestion(
    db: Session,
    *,
    user_id: int,
    raw_name: str,
) -> tuple[SkillSuggestion, bool]:
    normalized_name = normalize_text(raw_name)
    existing = (
        db.query(SkillSuggestion)
        .filter(
            SkillSuggestion.user_id == user_id,
            SkillSuggestion.normalized_name == normalized_name,
        )
        .first()
    )
    if existing is not None:
        return existing, False

    if find_skill(db, raw_name, user_id=user_id) is not None:
        raise ValueError(f"Skill is already recognized: {raw_name}")

    suggestion = SkillSuggestion(
        user_id=user_id,
        raw_name=raw_name.strip(),
        normalized_name=normalized_name,
        status="pending",
    )
    db.add(suggestion)
    try:
        db.commit()
        db.refresh(suggestion)
        return suggestion, True
    except IntegrityError:
        db.rollback()
        existing = (
            db.query(SkillSuggestion)
            .filter(
                SkillSuggestion.user_id == user_id,
                SkillSuggestion.normalized_name == normalized_name,
            )
            .first()
        )
        if existing is None:
            raise
        return existing, False


def list_suggestions(
    db: Session,
    *,
    user_id: int,
    status: str | None = None,
) -> list[SkillSuggestion]:
    query = (
        db.query(SkillSuggestion)
        .filter(SkillSuggestion.user_id == user_id)
    )
    if status is not None:
        query = query.filter(SkillSuggestion.status == status)
    return query.order_by(SkillSuggestion.id).all()


def resolve_suggestion(
    db: Session,
    *,
    user_id: int,
    suggestion_id: int,
    skill_id: int,
) -> SkillSuggestion:
    suggestion = (
        db.query(SkillSuggestion)
        .filter(
            SkillSuggestion.id == suggestion_id,
            SkillSuggestion.user_id == user_id,
        )
        .first()
    )
    if suggestion is None:
        raise LookupError(f"Skill suggestion not found: {suggestion_id}")

    skill = get_visible_skill(db, skill_id, user_id)
    if skill is None:
        raise LookupError(f"Skill not found: {skill_id}")

    suggestion.resolved_skill_id = skill.id
    suggestion.status = "accepted"
    db.commit()
    db.refresh(suggestion)
    return suggestion


def rank_skill_candidates(
    db: Session,
    *,
    user_id: int,
    suggestion_id: int,
    limit: int = 5,
) -> list[tuple[Skill, float]]:
    suggestion = (
        db.query(SkillSuggestion)
        .filter(
            SkillSuggestion.id == suggestion_id,
            SkillSuggestion.user_id == user_id,
        )
        .first()
    )
    if suggestion is None:
        raise LookupError(f"Skill suggestion not found: {suggestion_id}")
    if suggestion.status != "pending":
        raise ValueError("Candidates are only available for pending suggestions")

    query_text = normalize_text(suggestion.raw_name)
    query_candidate_text = _candidate_text(query_text)
    query_compact = _compact(query_candidate_text)
    if not query_compact:
        return []

    aliases_by_skill: dict[int, list[str]] = {}
    for alias in db.query(SkillAliases).all():
        aliases_by_skill.setdefault(alias.skill_id, []).append(alias.alias)
    for alias in db.query(PersonalSkillAlias).filter(PersonalSkillAlias.user_id == user_id).all():
        aliases_by_skill.setdefault(alias.skill_id, []).append(alias.alias)

    ranked: list[tuple[Skill, float]] = []
    for skill in visible_skills(db, user_id).all():
        known_names = [skill.name, *aliases_by_skill.get(skill.id, [])]
        best_score = max(
            (_similarity(query_text, query_compact, name) for name in known_names),
            default=0.0,
        )
        if best_score >= 0.25:
            ranked.append((skill, best_score))

    ranked.sort(key=lambda item: (-item[1], item[0].name.casefold()))
    return [(skill, round(score, 4)) for skill, score in ranked[:limit]]


def _compact(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", value)


def _candidate_text(value: str) -> str:
    normalized = normalize_text(value)
    return _CANDIDATE_TEXT_ALIASES.get(normalized, normalized)


def _similarity(query_text: str, _query_compact: str, known_name: str) -> float:
    known_text = normalize_text(known_name)
    query_candidate_text = _candidate_text(query_text)
    known_candidate_text = _candidate_text(known_text)
    query_compact = _compact(query_candidate_text)
    known_compact = _compact(known_candidate_text)
    if not known_compact:
        return 0.0
    if query_candidate_text == known_candidate_text:
        return 1.0
    if len(query_compact) < 2:
        return 0.0

    sequence_score = max(
        SequenceMatcher(None, query_candidate_text, known_candidate_text).ratio(),
        SequenceMatcher(None, query_compact, known_compact).ratio(),
    )
    query_tokens = set(re.findall(r"[a-z0-9]+", query_candidate_text))
    known_tokens = set(re.findall(r"[a-z0-9]+", known_candidate_text))
    shared_tokens = len(query_tokens & known_tokens)
    token_score = (
        2 * shared_tokens / (len(query_tokens) + len(known_tokens))
        if query_tokens and known_tokens
        else 0.0
    )
    return max(sequence_score, token_score * 0.9)
