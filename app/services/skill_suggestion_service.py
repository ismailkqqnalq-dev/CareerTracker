import re
from difflib import SequenceMatcher

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.skills import Skill, SkillAliases, SkillSuggestion
from app.services.skill_normalizer import find_skill, normalize_text


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

    skill = db.get(Skill, skill_id)
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
    query_compact = _compact(query_text)
    if len(query_compact) < 2:
        return []

    aliases_by_skill: dict[int, list[str]] = {}
    for alias in db.query(SkillAliases).all():
        aliases_by_skill.setdefault(alias.skill_id, []).append(alias.alias)

    ranked: list[tuple[Skill, float]] = []
    for skill in db.query(Skill).all():
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


def _similarity(query_text: str, query_compact: str, known_name: str) -> float:
    known_text = normalize_text(known_name)
    known_compact = _compact(known_text)
    if not known_compact:
        return 0.0
    if query_text == known_text or query_compact == known_compact:
        return 1.0

    sequence_score = max(
        SequenceMatcher(None, query_text, known_text).ratio(),
        SequenceMatcher(None, query_compact, known_compact).ratio(),
    )
    query_tokens = set(re.findall(r"[a-z0-9]+", query_text))
    known_tokens = set(re.findall(r"[a-z0-9]+", known_text))
    shared_tokens = len(query_tokens & known_tokens)
    token_score = (
        2 * shared_tokens / (len(query_tokens) + len(known_tokens))
        if query_tokens and known_tokens
        else 0.0
    )
    return max(sequence_score, token_score * 0.9)
