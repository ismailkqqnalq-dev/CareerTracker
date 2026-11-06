"""Compare lexical and semantic candidate ranking on a tiny synthetic set.

Requires the optional semantic extra and a pre-downloaded local model. Uses a
temporary in-memory SQLite database and prints metrics only; no examples are
read from or written to the user's database.
"""

import json
import os
import sys
from time import perf_counter

os.environ["PYTHON_DOTENV_DISABLED"] = "1"
os.environ["DATABASE_URL"] = "sqlite:///:memory:"

from sqlalchemy.orm import sessionmaker  # noqa: E402

from app.database.session import Base, create_database_engine  # noqa: E402
from app.models.skills import Skill, SkillSuggestion  # noqa: E402
from app.models.users import User  # noqa: E402
from app.services.semantic_skill_candidate_service import (  # noqa: E402
    SemanticEngineFailed,
    SemanticModelUnavailable,
    get_semantic_embedder,
    rank_semantic_skill_candidates,
)
from app.services.skill_catalog_service import seed_skill_catalog  # noqa: E402
from app.services.skill_normalizer import normalize_text  # noqa: E402
from app.services.skill_suggestion_service import rank_skill_candidates  # noqa: E402


SYNTHETIC_CASES = (
    ("algoritmaların veriden öğrenmesini sağlama", "Machine Learning"),
    ("yapay sinir ağlarıyla model eğitimi", "Deep Learning"),
    ("fotoğraf ve videolardan nesne tanıma", "Computer Vision"),
    ("metinleri sınıflandırma ve anlamlandırma", "Natural Language Processing"),
    ("verilerden içgörü elde etme", "Data Science"),
    ("veri kümelerini inceleyip sonuç çıkarma", "Data Analysis"),
    ("Python'da tablo verisiyle çalışma", "pandas"),
    ("sayısal diziler ve matrislerle hesaplama", "NumPy"),
    ("tahmin modeli oluşturmak için Python kütüphanesi", "scikit-learn"),
    ("tensor tabanlı sinir ağı kütüphanesi", "PyTorch"),
    ("uygulamaları konteynerlere paketleme", "Docker"),
    ("container orchestration platform", "Kubernetes"),
    ("görsel bileşenlerle web arayüzü oluşturma", "React"),
    ("Python ile REST servisleri tasarlama", "FastAPI"),
    ("SQL kullanan ilişkisel veri deposu", "PostgreSQL"),
    ("işlevsel bileşenlerle kullanıcı arayüzü geliştirme", "React"),
)


def _metrics(rows: list[tuple[str, list[str]]]) -> dict[str, float | int]:
    if not rows:
        return {"top1": 0, "top3": 0, "mrr_at_10": 0.0}
    top1 = top3 = 0
    reciprocal_ranks = []
    for expected, names in rows:
        try:
            rank = names.index(expected) + 1
        except ValueError:
            rank = None
        top1 += rank == 1
        top3 += rank is not None and rank <= 3
        reciprocal_ranks.append(1 / rank if rank is not None and rank <= 10 else 0.0)
    return {
        "top1": top1,
        "top3": top3,
        "mrr_at_10": round(sum(reciprocal_ranks) / len(rows), 4),
    }


def main() -> int:
    engine = create_database_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    db = sessionmaker(bind=engine, expire_on_commit=False)()
    try:
        user = User(email="semantic-evaluation@example.test", hashed_password="unused")
        db.add(user)
        db.commit()
        seed_skill_catalog(db)
        lexical_rows = []
        semantic_rows = []
        semantic_durations = []
        embedder = get_semantic_embedder()

        for index, (query, expected) in enumerate(SYNTHETIC_CASES):
            suggestion = SkillSuggestion(
                user_id=user.id,
                raw_name=query,
                normalized_name=f"evaluation-{index}",
                status="pending",
            )
            db.add(suggestion)
            db.commit()
            lexical = rank_skill_candidates(
                db,
                user_id=user.id,
                suggestion_id=suggestion.id,
                limit=10,
            )
            started = perf_counter()
            semantic = rank_semantic_skill_candidates(
                db,
                user_id=user.id,
                suggestion_id=suggestion.id,
                limit=10,
                embedder=embedder,
            )
            semantic_durations.append(perf_counter() - started)
            lexical_rows.append((expected, [skill.name for skill, _ in lexical]))
            semantic_rows.append((expected, [skill.name for skill, _ in semantic]))

        output = {
            "dataset": "small synthetic Turkish/English skill paraphrases",
            "examples": len(SYNTHETIC_CASES),
            "catalog_skills": db.query(Skill).count(),
            "lexical": _metrics(lexical_rows),
            "semantic": _metrics(semantic_rows),
            "semantic_first_call_seconds_including_lazy_model_load": round(
                semantic_durations[0], 3
            ),
            "semantic_warm_call_mean_ms": round(
                sum(semantic_durations[1:]) / max(1, len(semantic_durations) - 1) * 1000,
                2,
            ),
            "interpretation": "A small regression probe, not a real-world accuracy estimate.",
        }
        print(json.dumps(output, ensure_ascii=False, indent=2))
        return 0
    except (SemanticModelUnavailable, SemanticEngineFailed):
        print(
            'Semantic model unavailable. Install `.[semantic]` and run '
            '`python scripts/download_semantic_model.py` first.',
            file=sys.stderr,
        )
        return 2
    finally:
        db.close()
        Base.metadata.drop_all(engine)
        engine.dispose()


if __name__ == "__main__":
    raise SystemExit(main())
