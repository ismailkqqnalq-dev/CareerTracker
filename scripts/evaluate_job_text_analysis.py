"""Evaluate the rule-based job text matcher on a small synthetic dataset.

Run with ``python -m scripts.evaluate_job_text_analysis``. The evaluator uses
an in-memory SQLite database and writes its JSON report to stdout only.
"""

import json
import unicodedata

from sqlalchemy.orm import Session

from app.database.session import Base, create_database_engine
from app.models.skills import (
    PersonalSkillAlias,
    Skill,
    SkillAliases,
    SkillSuggestion,
    UserSkill,
)
from app.models.users import User
from app.services.job_text_analysis_service import analyze_job_text
from app.services.skill_catalog_service import seed_skill_catalog
from app.services.skill_normalizer import find_skill


SYNTHETIC_CASES = (
    {
        "id": "tr-clean",
        "text": (
            "Pozisyon: Backend Engineer\n"
            "Aranan Nitelikler:\nPython ve FastAPI deneyimi\n"
            "Tercihen:\nPostgreSQL'e aşinalık ve Redis bilgisi"
        ),
        "expected": ("Python", "FastAPI", "PostgreSQL", "Redis"),
        "unknown_terms": ("UncataloguedSkill",),
    },
    {
        "id": "en-clean",
        "text": (
            "Role: Frontend Engineer\nRequirements:\n"
            "React, TypeScript and Node.js experience\n"
            "Nice to have: Kubernetes"
        ),
        "expected": ("React", "TypeScript", "Node.js", "Kubernetes"),
        "unknown_terms": ("UncataloguedSkill",),
    },
    {
        "id": "symbols-and-short-name",
        "text": "C# programming experience; C++ is preferred; R notları",
        "expected": ("C#", "C++"),
        "unknown_terms": ("UncataloguedSkill",),
    },
    {
        "id": "ocr-like-noise",
        "text": "FastAP1 ile REST API; Postgre SQL deneyimi",
        "expected": ("FastAPI", "REST API", "PostgreSQL"),
        "unknown_terms": ("FastAP1",),
    },
    {
        "id": "turkish-ascii-ocr-folding",
        "text": "Pythön, FastAPI, JavaScript, C# ve C++",
        "expected": ("Python", "FastAPI", "JavaScript", "C#", "C++"),
        "unknown_terms": ("UncataloguedSkill",),
    },
    {
        "id": "unicode-decomposed-text",
        "text": unicodedata.normalize(
            "NFD",
            "Pozisyon: Veri Mühendisi\n"
            "İş İçin Gerekli Beceriler:\n"
            "Makine öğrenmesi deneyimi",
        ),
        "expected": ("Machine Learning",),
        "unknown_terms": ("UncataloguedSkill",),
    },
    {
        "id": "turkish-concept-aliases",
        "text": (
            "Makine öğrenmesi, derin öğrenme, doğal dil işleme ve "
            "bilgisayarlı görü; ayrıca veri analizi ve veri bilimi."
        ),
        "expected": (
            "Machine Learning",
            "Deep Learning",
            "Natural Language Processing",
            "Computer Vision",
            "Data Analysis",
            "Data Science",
        ),
        "unknown_terms": ("UncataloguedSkill",),
    },
    {
        "id": "folded-headings-and-sections",
        "text": (
            "Pozisyon: Veri Mühendisi\n"
            "İş İçin Gerekli Beceriler:\nPython\n"
            "Öne Çıkan Özellikler:\nPostgreSQL\n"
            "Hakkımızda:\nFastAPI"
        ),
        "expected": ("Python", "PostgreSQL", "FastAPI"),
        "unknown_terms": ("UncataloguedSkill",),
    },
    {
        "id": "ambiguous-short-terms",
        "text": (
            "C programming experience.\n"
            "R programlama dili deneyimi.\n"
            "Go programming language experience.\n"
            "Go board games.\nR&D team.\nC-level communication."
        ),
        "expected": ("C", "R", "Go"),
        "unknown_terms": ("UncataloguedSkill",),
    },
    {
        "id": "phrase-overlap",
        "text": "React Native and React; SQL Server and PostgreSQL; C# and C++.",
        "expected": (
            "React Native",
            "React",
            "Microsoft SQL Server",
            "PostgreSQL",
            "C#",
            "C++",
        ),
        "unknown_terms": ("UncataloguedSkill",),
    },
    {
        "id": "unknown-terms",
        "text": "DefinitelyUncataloguedTerm; UnknownFrameworkX; Kubernetes.",
        "expected": ("Kubernetes",),
        "unknown_terms": ("DefinitelyUncataloguedTerm", "UnknownFrameworkX"),
    },
)


def _scores(expected: set[str], predicted: set[str]) -> dict[str, int | float]:
    true_positive = len(expected & predicted)
    false_positive = len(predicted - expected)
    false_negative = len(expected - predicted)
    precision = true_positive / len(predicted) if predicted else 0.0
    recall = true_positive / len(expected) if expected else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return {
        "true_positive": true_positive,
        "false_positive": false_positive,
        "false_negative": false_negative,
        "precision": round(precision, 4),
        "recall": round(recall, 4),
        "f1": round(f1, 4),
    }


def evaluate(analyzer=analyze_job_text) -> dict:
    engine = create_database_engine("sqlite:///:memory:")
    tables = [
        User.__table__,
        Skill.__table__,
        SkillAliases.__table__,
        PersonalSkillAlias.__table__,
        SkillSuggestion.__table__,
        UserSkill.__table__,
    ]
    Base.metadata.create_all(bind=engine, tables=tables)

    with Session(engine) as db:
        seed_skill_catalog(db)
        user_id = 1
        rows = []
        total_tp = total_fp = total_fn = 0

        for case in SYNTHETIC_CASES:
            result = analyzer(db, user_id=user_id, text=case["text"])
            predicted = {skill["name"] for skill in result["skills"]}
            expected = set(case["expected"])
            scores = _scores(expected, predicted)
            total_tp += scores["true_positive"]
            total_fp += scores["false_positive"]
            total_fn += scores["false_negative"]
            unresolved = [
                term for term in case["unknown_terms"]
                if find_skill(db, term, user_id=user_id) is None
            ]
            rows.append({
                "id": case["id"],
                "role": result["role"],
                "expected": sorted(expected),
                "predicted": sorted(predicted),
                "scores": scores,
                "catalog_unresolved_terms": unresolved,
            })

        precision = total_tp / (total_tp + total_fp) if total_tp + total_fp else 0.0
        recall = total_tp / (total_tp + total_fn) if total_tp + total_fn else 0.0
        f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
        return {
            "method": "catalog and alias phrase matching with conservative section/role labels",
            "dataset": "synthetic only; no real job posts or personal data",
            "catalog": {
                "skills": db.query(Skill).count(),
                "global_aliases": db.query(SkillAliases).count(),
            },
            "aggregate_micro": {
                "true_positive": total_tp,
                "false_positive": total_fp,
                "false_negative": total_fn,
                "precision": round(precision, 4),
                "recall": round(recall, 4),
                "f1": round(f1, 4),
            },
            "cases": rows,
            "limitations": [
                "This small, hand-written synthetic sample is not representative of real job descriptions.",
                "Scores are regression signals for known cases, not estimates of real-world accuracy.",
                "OCR-like spelling noise is included to expose misses; no correction model is used.",
                "Unresolved terms are reported only and are not persisted as suggestions.",
            ],
        }


if __name__ == "__main__":
    # Keep the JSON portable to Windows consoles using legacy code pages.
    print(json.dumps(evaluate(), ensure_ascii=True, indent=2))
