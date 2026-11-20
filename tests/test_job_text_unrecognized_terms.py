"""Beceri listesi satırlarında katalogda olmayan terimleri öneri adayı olarak raporlama."""

from app.services.job_text_analysis_service import analyze_job_text
from app.services.skill_catalog_service import seed_skill_catalog


def _terms(db_session, text):
    seed_skill_catalog(db_session)
    result = analyze_job_text(db_session, user_id=1, text=text)
    return [(item["term"], item["line_number"]) for item in result["unrecognized_terms"]]


def test_reports_unknown_items_in_a_list_with_recognized_skills(db_session):
    text = "Pozisyon: Backend Engineer\nPython, Docker, Zedflux ve Quorabase"

    assert _terms(db_session, text) == [("Zedflux", 2), ("Quorabase", 2)]


def test_ignores_a_sentence_with_a_single_recognized_skill(db_session):
    text = "Python ile backend geliştirme, takım çalışması"

    assert _terms(db_session, text) == []


def test_ignores_generic_words_and_long_phrases_in_skill_lists(db_session):
    text = "\n".join([
        "Python, SQL and cloud experience",
        "Python, Docker, büyük ölçekli dağıtık sistem tasarımı",
        "Python, Docker vb.",
    ])

    assert _terms(db_session, text) == []


def test_drops_a_leading_label_and_keeps_the_term_after_it(db_session):
    text = "Teknolojiler: Zedflux, Python, Docker"

    assert _terms(db_session, text) == [("Zedflux", 1)]


def test_reports_each_term_once_with_its_first_line(db_session):
    text = "Python, Docker, Zedflux\nPython; Docker; zedflux"

    assert _terms(db_session, text) == [("Zedflux", 1)]


def test_does_not_split_slash_joined_terms(db_session):
    text = "Python, Docker, Zed/Flux"

    assert _terms(db_session, text) == [("Zed/Flux", 1)]


def test_api_returns_unrecognized_terms_using_the_users_visible_skills(authenticated_client):
    for name in ("Alphaskill", "Betaskill"):
        response = authenticated_client.post("/skills", json={"name": name, "category": "tool"})
        assert response.status_code == 201

    response = authenticated_client.post(
        "/job-analysis",
        json={"text": "Gereksinimler\nAlphaskill, Betaskill, Gammaskill"},
    )

    assert response.status_code == 200
    assert response.json()["unrecognized_terms"] == [{"term": "Gammaskill", "line_number": 2}]
