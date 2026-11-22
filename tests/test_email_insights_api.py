"""POST /email-insights/analyze: eşleştirme, öneriler ve hiçbir şeyin kaydedilmemesi."""

import pytest

from app.models.opportunity import Opportunity
from app.models.tasks import Task
from app.services.email_insight_service import sender_company_label

TODAY = "2026-11-22"
REJECTION = "Başvurunuz için teşekkür ederiz. Maalesef başka bir adayla ilerleme kararı aldık. Başarılar dileriz."
INTERVIEW = "Başvurunuzu inceledik ve sizinle bir ön görüşme yapmak istiyoruz. Uygun olduğunuz saatleri paylaşır mısınız?"
ASSESSMENT = "Süreç kapsamında online kodlama testini aşağıdaki bağlantıdan 5 gün içinde tamamlamanızı rica ederiz."
OFFER = "Size pozisyon için iş teklifimizi sunmaktan memnuniyet duyarız. Ücret ve yan haklar ektedir."
NEWSLETTER = "Profiline uygun 12 yeni iş ilanı yayınlandı. Hemen başvur."


def create(client, company, status="Başvuruldu", headers=None):
    response = client.post("/opportunities", headers=headers, json={
        "company": company, "position": "Backend", "type": "İş", "application_date": "2026-11-01",
        "job_link": "", "salary": 0, "location": "İzmir", "status": status, "notes": "",
        "next_action": "", "last_contact_date": "2026-11-10",
    })
    assert response.status_code == 200, response.text
    return response.json()["id"]


def analyze(client, body, **extra):
    response = client.post("/email-insights/analyze", json={"body": body, "today": TODAY, **extra})
    assert response.status_code == 200, response.text
    return response.json()


@pytest.mark.parametrize(
    ("sender", "label"),
    [
        ("Trendyol İK <ik@careers.trendyol.com>", "trendyol"),
        ("noreply@garanti.com.tr", "garanti"),
        ("Recruiting <no-reply@greenhouse.io>", None),
        ("ayse@gmail.com", None),
        ("", None),
    ],
)
def test_sender_domain_is_reduced_to_the_company_label(sender, label):
    assert sender_company_label(sender) == label


def test_matches_by_sender_domain_and_suggests_rejection(authenticated_client):
    opportunity_id = create(authenticated_client, "Trendyol")
    create(authenticated_client, "Getir")

    result = analyze(authenticated_client, REJECTION, sender="Trendyol İK <ik@careers.trendyol.com>", subject="Başvurunuz hakkında")

    assert result["type"] == "ret"
    assert result["opportunity"]["id"] == opportunity_id
    assert result["suggestion"] == {"status": "Reddedildi", "last_contact_date": TODAY, "task": None}
    assert "Trendyol" in result["explanation"]


def test_matches_by_company_name_in_the_text_through_a_platform_sender(authenticated_client):
    opportunity_id = create(authenticated_client, "Aselsan")

    result = analyze(authenticated_client, "Aselsan'daki başvurunuz için teşekkürler. " + REJECTION, sender="no-reply@myworkdayjobs.com")

    assert result["opportunity"]["id"] == opportunity_id


@pytest.mark.parametrize(
    ("current", "expected"),
    [("Başvuruldu", "Ön görüşme"), ("Ön görüşme", "Teknik mülakat"), ("Teknik mülakat", "Son mülakat"), ("Son mülakat", None)],
)
def test_interview_invitation_moves_one_stage_forward(authenticated_client, current, expected):
    opportunity_id = create(authenticated_client, "Insider", status=current)

    result = analyze(authenticated_client, INTERVIEW, opportunity_id=opportunity_id)

    assert result["type"] == "mulakat_daveti"
    assert result["suggestion"]["status"] == expected


def test_assessment_suggests_a_task_without_changing_status(authenticated_client):
    opportunity_id = create(authenticated_client, "Papara")

    suggestion = analyze(authenticated_client, ASSESSMENT, opportunity_id=opportunity_id)["suggestion"]

    assert suggestion["status"] is None
    assert suggestion["task"] == {"description": "Papara değerlendirmesini (test/ödev) tamamla", "due_date": "2026-11-25"}


def test_offer_suggests_the_offer_status(authenticated_client):
    opportunity_id = create(authenticated_client, "Baykar", status="Son mülakat")

    assert analyze(authenticated_client, OFFER, opportunity_id=opportunity_id)["suggestion"]["status"] == "Teklif"


def test_unrelated_email_suggests_nothing(authenticated_client):
    opportunity_id = create(authenticated_client, "Logo")

    result = analyze(authenticated_client, NEWSLETTER, opportunity_id=opportunity_id)

    assert result["type"] == "diger"
    assert result["suggestion"] == {"status": None, "last_contact_date": None, "task": None}


def test_ambiguous_match_returns_candidates_instead_of_guessing(authenticated_client):
    create(authenticated_client, "Turkcell")
    create(authenticated_client, "Turkcell Teknoloji")

    result = analyze(authenticated_client, "Turkcell başvurunuzla ilgili: " + REJECTION)

    assert result["opportunity"] is None
    assert len(result["candidates"]) == 2
    assert result["suggestion"]["status"] is None


def test_no_match_explains_and_suggests_nothing(authenticated_client):
    create(authenticated_client, "Vestel")

    result = analyze(authenticated_client, REJECTION, sender="ik@baskabirsirket.com")

    assert result["opportunity"] is None and result["candidates"] == []
    assert "eşleştiremedim" in result["explanation"]


def test_analysis_never_writes_to_the_database(authenticated_client, db_session):
    opportunity_id = create(authenticated_client, "Peak")
    before = db_session.query(Opportunity).filter_by(id=opportunity_id).one().status

    analyze(authenticated_client, ASSESSMENT, opportunity_id=opportunity_id)
    analyze(authenticated_client, REJECTION, opportunity_id=opportunity_id)

    db_session.expire_all()
    assert db_session.query(Opportunity).filter_by(id=opportunity_id).one().status == before
    assert db_session.query(Task).count() == 0


def test_never_matches_or_reveals_another_users_opportunity(authenticated_client):
    authenticated_client.post("/auth/register", json={"email": "other@example.com", "password": "OtherPass123"})
    token = authenticated_client.post(
        "/auth/token", data={"username": "other@example.com", "password": "OtherPass123"}
    ).json()["access_token"]
    foreign = create(authenticated_client, "Gizli Şirket", headers={"Authorization": f"Bearer {token}"})

    unmatched = analyze(authenticated_client, "Gizli Şirket: " + REJECTION, sender="ik@gizlisirket.com")
    by_id = authenticated_client.post("/email-insights/analyze", json={"body": REJECTION, "opportunity_id": foreign})

    assert unmatched["opportunity"] is None and unmatched["candidates"] == []
    assert by_id.status_code == 404


def test_response_is_not_cached_and_input_is_validated(authenticated_client):
    ok = authenticated_client.post("/email-insights/analyze", json={"body": NEWSLETTER})
    assert ok.headers["Cache-Control"] == "no-store"
    for body in ({"body": "   "}, {"body": "a" * 20_001}, {"body": "x", "extra": 1}):
        assert authenticated_client.post("/email-insights/analyze", json=body).status_code == 422


def test_requires_authentication(client):
    assert client.post("/email-insights/analyze", json={"body": REJECTION}).status_code == 401
