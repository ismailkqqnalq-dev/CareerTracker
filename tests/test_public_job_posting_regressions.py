import pytest

from app.services.job_text_analysis_service import analyze_job_text
from app.services.skill_catalog_service import seed_skill_catalog
from scripts.evaluate_public_job_postings import PUBLIC_POSTING_EXCERPTS, evaluate


@pytest.mark.parametrize(
    "case",
    PUBLIC_POSTING_EXCERPTS,
    ids=[case["id"] for case in PUBLIC_POSTING_EXCERPTS],
)
def test_public_posting_excerpt_role_and_skill_extraction(db_session, case):
    seed_skill_catalog(db_session)

    result = analyze_job_text(db_session, user_id=1, text=case["text"])
    assert result["role"] == case["role"], case["id"]

    skills_by_section = {"required": set(), "preferred": set(), "unspecified": set()}
    for skill in result["skills"]:
        for occurrence in skill["occurrences"]:
            skills_by_section[occurrence["section"]].add(skill["name"])

    for section, actual in skills_by_section.items():
        expected = case.get(section)
        if expected is not None:
            assert actual == expected, {
                "case": case["id"],
                "section": section,
                "missing": sorted(expected - actual),
                "extra": sorted(actual - expected),
            }


def test_go_is_recognized_from_language_list_but_not_board_game_context(db_session):
    seed_skill_catalog(db_session)

    listed = analyze_job_text(
        db_session,
        user_id=1,
        text="Python, Scala, Java; Go is a plus.",
    )
    assert "Go" in {skill["name"] for skill in listed["skills"]}

    unrelated = analyze_job_text(
        db_session,
        user_id=1,
        text="Go board games; Python experience is useful.",
    )
    assert "Go" not in {skill["name"] for skill in unrelated["skills"]}


def test_public_posting_evaluator_is_small_explicit_and_in_memory(monkeypatch):
    import scripts.evaluate_public_job_postings as evaluator

    create_engine = evaluator.create_database_engine
    database_urls = []

    def capture_database_url(database_url):
        database_urls.append(database_url)
        return create_engine(database_url)

    monkeypatch.setattr(evaluator, "create_database_engine", capture_database_url)
    report = evaluate()

    assert database_urls == ["sqlite:///:memory:"]
    assert report["dataset"].startswith("seven short")
    assert len(report["cases"]) == len(PUBLIC_POSTING_EXCERPTS)
    assert "not representative of real-world accuracy" in report["dataset"]
    intropic = next(case for case in report["cases"] if case["id"] == "intropic-software-engineer")
    trendyol = next(case for case in report["cases"] if case["id"] == "trendyol-data-engineer")
    assert intropic["catalog_uncovered"] == ["Rust"]
    assert trendyol["catalog_uncovered"] == ["Scala"]
    assert "excluded" in report["metric_scope"]
    assert 0 <= report["role_accuracy"] <= 1
    assert set(report["aggregate_micro"]) >= {
        "precision", "recall", "f1", "false_positive", "false_negative"
    }
