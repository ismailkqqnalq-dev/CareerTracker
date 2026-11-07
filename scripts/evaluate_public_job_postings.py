"""Evaluate short, skill-focused excerpts from public job postings.

Run with ``python -m scripts.evaluate_public_job_postings``. Only titles,
section labels, and technical names are retained; no full job descriptions or
applicant data are included. The hand-annotated sample is a regression check,
not a representative estimate of production accuracy.
"""

import json

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


PUBLIC_POSTING_EXCERPTS = (
    {
        "id": "shyftlabs-data-engineer",
        "source": "https://jobs.lever.co/shyftlabs/9f947999-ea46-4627-bf08-fe3f3ebac513",
        "retrieved": "2026-11-07",
        "text": (
            "Data Engineer\nBasic Qualifications:\n"
            "Python, SQL, Git, Databricks, GCP, AWS, Azure, MongoDB, "
            "Elasticsearch, Airflow, Hadoop, Docker\n"
            "Preferred Qualifications:\nApache Spark"
        ),
        "role": "Data Engineer",
        "required": {
            "Python", "SQL", "Git", "Databricks", "Google Cloud Platform",
            "AWS", "Microsoft Azure", "MongoDB", "Elasticsearch",
            "Apache Airflow", "Apache Hadoop", "Docker",
        },
        "preferred": {"Apache Spark"},
    },
    {
        "id": "h1-data-engineer-life-sciences",
        "source": "https://jobs.lever.co/h1/504c27cd-7c6f-442e-912c-524ba6b10792",
        "retrieved": "2026-11-07",
        "text": (
            "Data Engineer II\nREQUIREMENTS\n"
            "Python, PySpark, SQL; pipeline orchestration tools: Argo, "
            "Airflow, Databricks; AWS services: S3, Lambda, ECS"
        ),
        "role": "Data Engineer II",
        "required": {
            "Python", "Apache Spark", "SQL", "Apache Airflow", "Databricks",
            "AWS", "Amazon S3", "AWS Lambda", "Amazon ECS",
        },
        "preferred": set(),
    },
    {
        "id": "trendyol-data-engineer",
        "source": "https://jobs.lever.co/trendyol/eaa523a4-5e9e-4b4a-b674-ee7906be309c",
        "retrieved": "2026-11-07",
        "text": (
            "Data Engineer\nExpected Qualifications:\n"
            "Software engineering skills: Python, Scala, Java, Go; "
            "Spark, Flink, SQL, Docker, Kubernetes and CI/CD"
        ),
        "role": "Data Engineer",
        "required": {
            "Python", "Java", "Go", "Apache Spark", "Apache Flink",
            "SQL", "Docker", "Kubernetes", "CI/CD",
        },
        "preferred": set(),
        "catalog_uncovered": {"Scala"},
    },
    {
        "id": "quantlane-data-engineer",
        "source": "https://jobs.lever.co/quantlane/55d1323f-0d1e-42ac-8be8-62b785746e8b",
        "retrieved": "2026-11-07",
        "text": (
            "Data engineer (Python)\nOur stack: Python, Airflow, Docker, "
            "PostgreSQL, Kubernetes, AWS, S3, EC2, ClickHouse, "
            "Apache Iceberg, DuckDB, Trino"
        ),
        "role": "Data engineer (Python)",
        "required": set(),
        "preferred": set(),
        "unspecified": {
            "Python", "Apache Airflow", "Docker", "PostgreSQL", "Kubernetes",
            "AWS", "Amazon S3", "Amazon EC2", "ClickHouse", "Apache Iceberg",
            "DuckDB", "Trino",
        },
    },
    {
        "id": "intropic-software-engineer",
        "source": "https://jobs.lever.co/intropic/4649bd22-9d7b-4927-a367-d1a47985dc67",
        "retrieved": "2026-11-07",
        "text": (
            "Software Engineer\nRequirements\n"
            "Python, REST APIs, SQL\n"
            "Nice-to-have\nRust, AWS"
        ),
        "role": "Software Engineer",
        "required": {"Python", "REST API", "SQL"},
        "preferred": {"AWS"},
        # The catalog intentionally has no bare "rust" alias because it is an
        # ambiguous ordinary word; keep the observed catalog-coverage gap visible.
        "catalog_uncovered": {"Rust"},
    },
    {
        "id": "kitware-machine-learning-engineer",
        "source": "https://jobs.lever.co/kitware/131535ab-7059-448c-bf96-0b2137008f57",
        "retrieved": "2026-11-07",
        "text": (
            "Machine Learning Engineer\nRequired Qualifications:\n"
            "Python, PyTorch, TensorFlow, machine learning, computer vision, "
            "natural language processing\nPreferred Qualifications:\nC++"
        ),
        "role": "Machine Learning Engineer",
        "required": {
            "Python", "PyTorch", "TensorFlow", "Machine Learning",
            "Computer Vision", "Natural Language Processing",
        },
        "preferred": {"C++"},
        "unspecified": {"Machine Learning"},
    },
    {
        "id": "reply-devops-engineer",
        "source": "https://jobs.lever.co/reply/8c3c1e8d-3313-4e3f-829f-4a9e7506fd43",
        "retrieved": "2026-11-07",
        "text": (
            "DevOps Engineer\nMinimum Requirements:\n"
            "Kubernetes, CI/CD, Google Cloud Platform, Istio\n"
            "Preferred Qualifications:\nTerraform"
        ),
        "role": "DevOps Engineer",
        "required": {"Kubernetes", "CI/CD", "Google Cloud Platform", "Istio"},
        "preferred": {"Terraform"},
    },
)


def _scores(expected: set[tuple[str, str]], predicted: set[tuple[str, str]]) -> dict:
    true_positive = len(expected & predicted)
    false_positive = len(predicted - expected)
    false_negative = len(expected - predicted)
    precision = true_positive / len(predicted) if predicted else 0.0
    recall = true_positive / len(expected) if expected else 0.0
    f1 = (
        2 * precision * recall / (precision + recall)
        if precision + recall
        else 0.0
    )
    return {
        "true_positive": true_positive,
        "false_positive": false_positive,
        "false_negative": false_negative,
        "precision": round(precision, 4),
        "recall": round(recall, 4),
        "f1": round(f1, 4),
    }


def evaluate() -> dict:
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
        rows = []
        all_expected: set[tuple[str, str]] = set()
        all_predicted: set[tuple[str, str]] = set()
        role_correct = 0

        for case in PUBLIC_POSTING_EXCERPTS:
            result = analyze_job_text(db, user_id=1, text=case["text"])
            expected = {
                (section, name)
                for section in ("required", "preferred", "unspecified")
                for name in case.get(section, set())
            }
            predicted = {
                (occurrence["section"], skill["name"])
                for skill in result["skills"]
                for occurrence in skill["occurrences"]
            }
            all_expected.update(expected)
            all_predicted.update(predicted)
            role_matches = result["role"] == case["role"]
            role_correct += int(role_matches)
            rows.append({
                "id": case["id"],
                "source": case["source"],
                "retrieved": case["retrieved"],
                "role_expected": case["role"],
                "role_predicted": result["role"],
                "role_correct": role_matches,
                "catalog_uncovered": sorted(case.get("catalog_uncovered", set())),
                "expected": sorted(f"{section}:{name}" for section, name in expected),
                "predicted": sorted(f"{section}:{name}" for section, name in predicted),
                "missing": sorted(f"{section}:{name}" for section, name in expected - predicted),
                "extra": sorted(f"{section}:{name}" for section, name in predicted - expected),
            })

        return {
            "method": "rule-based catalog and alias matching; explicit/headline role parsing",
            "dataset": (
                "seven short, manually annotated excerpts from public job postings; "
                "not full descriptions and not representative of real-world accuracy"
            ),
            "retrieved": "2026-11-07",
            "catalog": {
                "skills": db.query(Skill).count(),
                "global_aliases": db.query(SkillAliases).count(),
            },
            "role_accuracy": round(role_correct / len(rows), 4),
            "aggregate_micro": _scores(all_expected, all_predicted),
            "metric_scope": (
                "Skill scores cover expected names represented in the seeded catalog; "
                "catalog_uncovered entries are reported separately and excluded."
            ),
            "cases": rows,
            "limitations": [
                "The sample spans data engineering, software engineering, machine learning, and DevOps, but remains small.",
                "Expected terms are manually selected from each source page.",
                "Ambiguous bare names intentionally excluded by the catalog are reported separately, not counted as extraction false negatives.",
                "The excerpts test text analysis, not OCR image recognition.",
                "Results are regression evidence, not a production accuracy estimate.",
            ],
        }


if __name__ == "__main__":
    print(json.dumps(evaluate(), ensure_ascii=True, indent=2))
