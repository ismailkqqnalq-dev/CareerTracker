"""Optional, local semantic ranking for pending skill suggestions.

The lexical candidate ranker remains the default. This module only loads the
optional FastEmbed dependency when the semantic strategy is explicitly used.
"""

from collections import OrderedDict
from math import fsum, sqrt
from threading import RLock
from typing import Protocol, Sequence

from sqlalchemy.orm import Session

from app.models.skills import PersonalSkillAlias, Skill, SkillAliases, SkillSuggestion
from app.services.skill_access import visible_skills


SEMANTIC_MODEL_NAME = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
MAX_CACHED_CATALOGS = 8


class SemanticModelUnavailable(RuntimeError):
    """The optional runtime or its locally cached model is unavailable."""


class SemanticEngineFailed(RuntimeError):
    """The local embedding runtime failed to encode text."""


class SemanticEmbedder(Protocol):
    def embed_texts(self, texts: Sequence[str]) -> Sequence[Sequence[float]]: ...


class FastEmbedSemanticEmbedder:
    """Lazy CPU encoder; inference uses only the already downloaded local model."""

    def __init__(self) -> None:
        self._model = None
        self._lock = RLock()

    def _get_model(self):
        if self._model is not None:
            return self._model

        try:
            from fastembed import TextEmbedding
        except ImportError as error:
            raise SemanticModelUnavailable from error

        try:
            self._model = TextEmbedding(
                model_name=SEMANTIC_MODEL_NAME,
                threads=2,
                local_files_only=True,
            )
        except Exception as error:
            # Never let the first API request start an implicit network download.
            raise SemanticModelUnavailable from error
        return self._model

    def embed_texts(self, texts: Sequence[str]) -> Sequence[Sequence[float]]:
        if not texts:
            return []
        with self._lock:
            model = self._get_model()
            try:
                return [tuple(float(value) for value in row) for row in model.embed(texts, batch_size=32)]
            except Exception as error:
                raise SemanticEngineFailed from error


def prepare_semantic_model() -> None:
    """Explicitly download and initialize the optional model for local use."""
    try:
        from fastembed import TextEmbedding
    except ImportError as error:
        raise SemanticModelUnavailable from error

    try:
        model = TextEmbedding(
            model_name=SEMANTIC_MODEL_NAME,
            threads=2,
            local_files_only=False,
        )
        # Force ONNX initialization while encoding a fixed, non-user string.
        next(iter(model.embed(["CareerTracker semantic model warm-up"])))
    except Exception as error:
        raise SemanticModelUnavailable from error


_DEFAULT_EMBEDDER = FastEmbedSemanticEmbedder()
_CATALOG_CACHE_LOCK = RLock()
_CATALOG_VECTOR_CACHE: OrderedDict[tuple, tuple[tuple[int, tuple[float, ...]], ...]] = OrderedDict()


def get_semantic_embedder() -> SemanticEmbedder:
    return _DEFAULT_EMBEDDER


def clear_semantic_candidate_cache() -> None:
    """Clear process-local candidate embeddings (used by tests and maintenance)."""
    with _CATALOG_CACHE_LOCK:
        _CATALOG_VECTOR_CACHE.clear()


def _suggestion_for_user(db: Session, *, user_id: int, suggestion_id: int) -> SkillSuggestion:
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
    return suggestion


def _catalog_signature(
    skills: Sequence[Skill],
    aliases_by_skill: dict[int, list[str]],
) -> tuple:
    return tuple(
        (
            skill.id,
            skill.name,
            skill.category or "",
            tuple(sorted(set(aliases_by_skill.get(skill.id, [])))),
        )
        for skill in skills
    )


def _catalog_vectors(
    skills: Sequence[Skill],
    aliases_by_skill: dict[int, list[str]],
    *,
    embedder: SemanticEmbedder,
) -> tuple[tuple[int, tuple[float, ...]], ...]:
    signature = _catalog_signature(skills, aliases_by_skill)
    cacheable = isinstance(embedder, FastEmbedSemanticEmbedder)
    if cacheable:
        with _CATALOG_CACHE_LOCK:
            cached = _CATALOG_VECTOR_CACHE.get(signature)
            if cached is not None:
                _CATALOG_VECTOR_CACHE.move_to_end(signature)
                return cached

    texts: list[str] = []
    skill_ids: list[int] = []
    for skill in skills:
        phrases = dict.fromkeys([skill.name, *aliases_by_skill.get(skill.id, [])])
        for phrase in phrases:
            texts.append(phrase)
            skill_ids.append(skill.id)
            if skill.category:
                texts.append(f"{phrase}. Category: {skill.category}")
                skill_ids.append(skill.id)

    vectors = embedder.embed_texts(texts)
    if len(vectors) != len(skill_ids):
        raise SemanticEngineFailed("Embedding count did not match candidate text count")
    encoded = tuple(
        (skill_id, tuple(vector))
        for skill_id, vector in zip(skill_ids, vectors)
    )

    if cacheable:
        with _CATALOG_CACHE_LOCK:
            _CATALOG_VECTOR_CACHE[signature] = encoded
            _CATALOG_VECTOR_CACHE.move_to_end(signature)
            while len(_CATALOG_VECTOR_CACHE) > MAX_CACHED_CATALOGS:
                _CATALOG_VECTOR_CACHE.popitem(last=False)
    return encoded


def _cosine_similarity(left: Sequence[float], right: Sequence[float]) -> float:
    if len(left) != len(right) or not left:
        raise SemanticEngineFailed("Embedding vectors have incompatible dimensions")
    left_norm = sqrt(fsum(value * value for value in left))
    right_norm = sqrt(fsum(value * value for value in right))
    if not left_norm or not right_norm:
        return 0.0
    return fsum(a * b for a, b in zip(left, right)) / (left_norm * right_norm)


def rank_semantic_skill_candidates(
    db: Session,
    *,
    user_id: int,
    suggestion_id: int,
    limit: int = 5,
    embedder: SemanticEmbedder | None = None,
) -> list[tuple[Skill, float]]:
    suggestion = _suggestion_for_user(
        db,
        user_id=user_id,
        suggestion_id=suggestion_id,
    )
    skills = visible_skills(db, user_id).order_by(Skill.id).all()
    if not skills:
        return []

    visible_ids = [skill.id for skill in skills]
    aliases_by_skill: dict[int, list[str]] = {}
    for alias in (
        db.query(SkillAliases)
        .filter(SkillAliases.skill_id.in_(visible_ids))
        .order_by(SkillAliases.id)
        .all()
    ):
        aliases_by_skill.setdefault(alias.skill_id, []).append(alias.alias)
    for alias in (
        db.query(PersonalSkillAlias)
        .filter(
            PersonalSkillAlias.user_id == user_id,
            PersonalSkillAlias.skill_id.in_(visible_ids),
        )
        .order_by(PersonalSkillAlias.id)
        .all()
    ):
        aliases_by_skill.setdefault(alias.skill_id, []).append(alias.alias)

    active_embedder = embedder or get_semantic_embedder()
    catalog_vectors = _catalog_vectors(
        skills,
        aliases_by_skill,
        embedder=active_embedder,
    )
    query_vectors = active_embedder.embed_texts([suggestion.raw_name])
    if len(query_vectors) != 1:
        raise SemanticEngineFailed("Embedding count did not match query count")
    query_vector = query_vectors[0]

    scores = {skill.id: -1.0 for skill in skills}
    for skill_id, vector in catalog_vectors:
        scores[skill_id] = max(scores[skill_id], _cosine_similarity(query_vector, vector))

    skills_by_id = {skill.id: skill for skill in skills}
    ranked = sorted(
        ((skills_by_id[skill_id], score) for skill_id, score in scores.items()),
        key=lambda item: (-item[1], item[0].name.casefold()),
    )
    # API scores remain within the existing 0..1 schema; a score is similarity,
    # never a probability that the two labels mean the same thing.
    return [(skill, round(max(0.0, score), 4)) for skill, score in ranked[:limit]]
