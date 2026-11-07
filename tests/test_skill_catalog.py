import os
import subprocess
import sys

import pytest

from app.database.session import get_db
from app.main import app
from app.models.skills import Skill, SkillAliases
from app.services.skill_catalog_service import seed_skill_catalog
from app.services.job_text_analysis_service import _fold_for_matching
from app.services.job_text_analysis_service import analyze_job_text
from app.services.skill_normalizer import find_skill, normalize_text
from app.skill_catalog import SKILL_CATALOG


@pytest.fixture()
def db_session(client):
    db_generator = app.dependency_overrides[get_db]()
    db = next(db_generator)
    try:
        yield db
    finally:
        db_generator.close()


def test_seed_skill_catalog_is_idempotent(db_session):
    first_result = seed_skill_catalog(db_session)
    second_result = seed_skill_catalog(db_session)

    expected_aliases = {
        normalize_text(alias)
        for entry in SKILL_CATALOG
        for alias in (entry["name"], *entry["aliases"])
    }

    assert first_result == {
        "skills_created": len(SKILL_CATALOG),
        "aliases_created": len(expected_aliases),
    }
    assert second_result == {
        "skills_created": 0,
        "aliases_created": 0,
    }


def test_catalog_covers_common_technical_skills_and_stays_manageable():
    names = {entry["name"] for entry in SKILL_CATALOG}

    assert 120 <= len(SKILL_CATALOG) <= 220
    assert {
        "Python",
        "pandas",
        "NumPy",
        "scikit-learn",
        "PyTorch",
        "TensorFlow",
        "OpenCV",
        "Natural Language Processing",
        "Docker",
        "Git",
        "FastAPI",
        "Django",
        "Flask",
        "PostgreSQL",
        "AWS",
        "Kubernetes",
        "NoSQL",
        "Amazon SQS",
        "Flyte",
        "JUnit",
        "TestNG",
        "Gradle",
        "Apache Maven",
        "Swagger",
        "GitHub",
    } <= names


def test_catalog_covers_unmapped_technologies_observed_in_public_job_posts():
    names = {entry["name"] for entry in SKILL_CATALOG}

    assert {
        "Amazon S3",
        "Unity Catalog",
        "Delta Lake",
        "DuckLake",
        "Material UI",
        "Turborepo",
        "Yarn Workspaces",
        "tRPC",
        "RabbitMQ",
        "asyncio",
        "GitLab",
        "Metabase",
        "Streamlit",
        "Amazon EC2",
        "Apache Iceberg",
        "Trino",
    } <= names


def test_observed_job_stack_aliases_resolve_to_canonical_skills(db_session):
    seed_skill_catalog(db_session)

    expected = {
        "S3": "Amazon S3",
        "Databricks Unity Catalog": "Unity Catalog",
        "Delta Lakehouse": "Delta Lake",
        "Duck Lake": "DuckLake",
        "MUI": "Material UI",
        "Turbo Repo": "Turborepo",
        "Yarn Workspace": "Yarn Workspaces",
        "tRPC": "tRPC",
        "Rabbit MQ": "RabbitMQ",
    }
    for alias, canonical_name in expected.items():
        skill = find_skill(db_session, alias)
        assert skill is not None, alias
        assert skill.name == canonical_name, alias


def test_quantlane_stack_aliases_resolve_and_are_extracted(db_session):
    seed_skill_catalog(db_session)

    expected = {
        "asyncio": "asyncio",
        "GitLab": "GitLab",
        "Metabase": "Metabase",
        "Streamlit": "Streamlit",
        "EC2": "Amazon EC2",
        "Apache Iceberg": "Apache Iceberg",
        "Trino": "Trino",
    }
    for alias, canonical_name in expected.items():
        skill = find_skill(db_session, alias)
        assert skill is not None, alias
        assert skill.name == canonical_name, alias

    result = analyze_job_text(
        db_session,
        user_id=1,
        text=(
            "Our stack:\n"
            "asyncio, GitLab, Metabase, Streamlit, EC2, "
            "Apache Iceberg, Trino"
        ),
    )
    assert {skill["name"] for skill in result["skills"]} == set(expected.values())


def test_observed_job_stack_terms_are_extracted(db_session):
    seed_skill_catalog(db_session)

    result = analyze_job_text(
        db_session,
        user_id=1,
        text=(
            "Data Engineer\n"
            "Basic Qualifications:\n"
            "Amazon S3, Unity Catalog, Delta Lake, DuckLake, MUI, "
            "Turborepo, Yarn Workspaces, tRPC, RabbitMQ"
        ),
    )

    assert {skill["name"] for skill in result["skills"]} == {
        "Amazon S3",
        "Unity Catalog",
        "Delta Lake",
        "DuckLake",
        "Material UI",
        "Turborepo",
        "Yarn Workspaces",
        "tRPC",
        "RabbitMQ",
    }


def test_real_job_ad_terms_and_plural_rest_api_are_extracted(db_session):
    seed_skill_catalog(db_session)

    result = analyze_job_text(
        db_session,
        user_id=1,
        text=(
            "Minimum Requirements:\n"
            "REST APIs, NoSQL, Amazon SQS, Flyte\n"
            "Any of the following would be a bonus\n"
            "JUnit, TestNG, Gradle, Apache Maven, Swagger, GitHub"
        ),
    )

    found = {item["name"]: item for item in result["skills"]}
    assert {
        "REST API", "NoSQL", "Amazon SQS", "Flyte", "JUnit", "TestNG",
        "Gradle", "Apache Maven", "Swagger", "GitHub",
    } <= found.keys()
    assert found["REST API"]["occurrences"][0]["matched_text"] == "REST APIs"
    assert found["REST API"]["occurrences"][0]["section"] == "required"
    assert found["JUnit"]["occurrences"][0]["section"] == "preferred"


def test_real_job_ad_catalog_aliases_resolve_to_expected_canonical_names(db_session):
    seed_skill_catalog(db_session)

    expected = {
        "REST APIs": "REST API",
        "No SQL": "NoSQL",
        "SQS": "Amazon SQS",
        "Flyte workflow orchestration": "Flyte",
        "JUnit Jupiter": "JUnit",
        "Test NG": "TestNG",
        "Gradle build tool": "Gradle",
        "Maven": "Apache Maven",
        "Swagger UI": "Swagger",
        "github.com": "GitHub",
    }
    for alias, canonical_name in expected.items():
        skill = find_skill(db_session, alias)
        assert skill is not None, alias
        assert skill.name == canonical_name, alias


def test_turkish_machine_learning_alias_resolves_and_is_extracted(db_session):
    seed_skill_catalog(db_session)

    skill = find_skill(db_session, "Makine öğrenmesi")
    result = analyze_job_text(
        db_session,
        user_id=1,
        text="Makine öğrenmesi deneyimi",
    )

    assert skill is not None
    assert skill.name == "Machine Learning"
    assert [item["name"] for item in result["skills"]] == ["Machine Learning"]


def test_fastapi_ocr_digit_one_alias_resolves_and_is_extracted(db_session):
    seed_skill_catalog(db_session)

    skill = find_skill(db_session, "FastAP1")
    result = analyze_job_text(
        db_session,
        user_id=1,
        text="FastAP1 deneyimi",
    )

    assert skill is not None
    assert skill.name == "FastAPI"
    assert [item["name"] for item in result["skills"]] == ["FastAPI"]


def test_catalog_aliases_do_not_collide_across_skills_after_normalization_or_folding():
    normalized_owners = {}
    folded_owners = {}
    conflicts = []

    for entry in SKILL_CATALOG:
        for alias in (entry["name"], *entry["aliases"]):
            normalized = normalize_text(alias)
            folded = _fold_for_matching(normalized)
            for key, owners in (
                (normalized, normalized_owners),
                (folded, folded_owners),
            ):
                owner = owners.setdefault(key, entry["name"])
                if owner != entry["name"]:
                    conflicts.append((key, owner, entry["name"]))

    assert conflicts == []


def test_every_canonical_name_and_alias_resolves_to_its_seeded_skill(db_session):
    seed_skill_catalog(db_session)

    for entry in SKILL_CATALOG:
        for alias in (entry["name"], *entry["aliases"]):
            resolved = find_skill(db_session, alias)
            assert resolved is not None, alias
            assert resolved.name == entry["name"], alias


def test_ambiguous_short_language_names_keep_context_filter(db_session):
    seed_skill_catalog(db_session)

    result = analyze_job_text(
        db_session,
        user_id=1,
        text=(
            "C# programming experience\n"
            "Go board game\n"
            "R random variable\n"
            "C language experience\n"
            "R programming language\n"
            "Go programming language"
        ),
    )

    assert {skill["name"] for skill in result["skills"]} == {
        "C#", "C", "R", "Go"
    }


def test_postgre_sql_spacing_variant_resolves_as_postgresql(db_session):
    seed_skill_catalog(db_session)

    skill = find_skill(db_session, "Postgre SQL")
    result = analyze_job_text(db_session, user_id=1, text="Postgre SQL")

    assert skill is not None
    assert skill.name == "PostgreSQL"
    assert [item["name"] for item in result["skills"]] == ["PostgreSQL"]


def test_generic_ambiguous_terms_are_not_standalone_catalog_aliases():
    catalog_terms = {
        normalize_text(alias)
        for entry in SKILL_CATALOG
        for alias in (entry["name"], *entry["aliases"])
    }

    assert {
        "spring",
        "spark",
        "excel",
        "word",
        "dash",
        "flow",
        "unity",
        "swift",
        "rust",
        "ruby",
        "scala",
        "dart",
        "julia",
        "express",
        "requests",
        "airflow",
    }.isdisjoint(catalog_terms)


def test_seed_entrypoint_registers_user_metadata_on_fresh_database(tmp_path):
    database_path = tmp_path / "fresh-seed.db"
    script = """
from app.seed_skill_catalog import main
from app.database.session import Base, SessionLocal, engine
Base.metadata.create_all(bind=engine)
from app.models.users import User
from app.models.skills import PersonalSkillAlias, Skill
with SessionLocal() as db:
    user = User(email='seed-user@example.test', hashed_password='unused')
    db.add(user)
    db.flush()
    private_skill = Skill(name='Private seed fixture', category='tool', owner_user_id=user.id)
    db.add(private_skill)
    db.flush()
    alias = PersonalSkillAlias(user_id=user.id, alias='private seed alias', skill_id=private_skill.id)
    db.add(alias)
    db.commit()
main()
main()
with SessionLocal() as db:
    assert db.query(User).filter_by(email='seed-user@example.test').count() == 1
    assert db.query(Skill).filter_by(name='Private seed fixture').count() == 1
    assert db.query(PersonalSkillAlias).filter_by(alias='private seed alias').count() == 1
"""
    env = os.environ.copy()
    env["DATABASE_URL"] = f"sqlite:///{database_path.as_posix()}"
    env["PYTHON_DOTENV_DISABLED"] = "1"

    result = subprocess.run(
        [sys.executable, "-c", script],
        capture_output=True,
        text=True,
        env=env,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    expected_alias_count = len({
        normalize_text(alias)
        for entry in SKILL_CATALOG
        for alias in (entry["name"], *entry["aliases"])
    })
    assert (
        f"Skill catalog seeded: {len(SKILL_CATALOG)} skills, "
        f"{expected_alias_count} aliases added."
    ) in result.stdout
    assert "Skill catalog seeded: 0 skills, 0 aliases added." in result.stdout


def test_catalog_aliases_resolve_to_canonical_skill(db_session):
    seed_skill_catalog(db_session)

    python = find_skill(db_session, "  PY  ")
    postgres = find_skill(db_session, "Postgres")
    kubernetes = find_skill(db_session, "K8S")

    assert python is not None
    assert python.name == "Python"

    assert postgres is not None
    assert postgres.name == "PostgreSQL"

    assert kubernetes is not None
    assert kubernetes.name == "Kubernetes"


def test_seed_catalog_rejects_alias_owned_by_another_skill(db_session):
    other_skill = Skill(name="Unrelated Skill", category="other")
    db_session.add(other_skill)
    db_session.flush()
    db_session.add(
        SkillAliases(alias="py", skill_id=other_skill.id)
    )
    db_session.commit()

    with pytest.raises(ValueError, match="already belongs to another skill"):
        seed_skill_catalog(db_session)

    db_session.expire_all()
    assert (
        db_session.query(Skill)
        .filter(Skill.name == "Python")
        .first()
        is None
    )
