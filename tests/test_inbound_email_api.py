"""Yönlendirme adresi, POST /inbound/email, bekleyen öneriler ve asistanla bağlantı."""

import pytest

from app.models.email_insights import EmailSuggestion
from app.models.opportunity import Opportunity
from app.models.tasks import Task

SECRET = "test-inbound-secret-value"
DOMAIN = "gelen.example.test"
REJECTION = "Başvurunuz için teşekkür ederiz. Maalesef başka bir adayla ilerleme kararı aldık. Başarılar dileriz."
ASSESSMENT = "Süreç kapsamında online kodlama testini aşağıdaki bağlantıdan 5 gün içinde tamamlamanızı rica ederiz."
NEWSLETTER = "Profiline uygun 12 yeni iş ilanı yayınlandı. Hemen başvur."


@pytest.fixture(autouse=True)
def inbound_settings(monkeypatch):
    monkeypatch.setenv("INBOUND_EMAIL_SECRET", SECRET)
    monkeypatch.setenv("INBOUND_EMAIL_DOMAIN", DOMAIN)


def create(client, company, status="Başvuruldu", headers=None):
    response = client.post("/opportunities", headers=headers, json={
        "company": company, "position": "Backend", "type": "İş", "application_date": "2026-11-01",
        "job_link": "", "salary": 0, "location": "İzmir", "status": status, "notes": "",
        "next_action": "", "last_contact_date": "2026-11-10",
    })
    assert response.status_code == 200, response.text
    return response.json()["id"]


def address_of(client, headers=None):
    response = client.post("/email-insights/address", headers=headers)
    assert response.status_code == 200, response.text
    return response.json()["address"]


def deliver(client, recipient, text, *, sender="ik@careers.trendyol.com", subject="Başvurunuz hakkında", secret=SECRET):
    return client.post(
        "/inbound/email",
        headers={"X-Inbound-Secret": secret} if secret else {},
        json={"recipient": recipient, "sender": sender, "subject": subject, "text": text},
    )


def pending(client):
    response = client.get("/email-insights/suggestions")
    assert response.status_code == 200
    return response.json()


def test_address_is_created_shown_rotated_and_disabled(authenticated_client):
    assert authenticated_client.get("/email-insights/address").json()["enabled"] is False

    first = address_of(authenticated_client)
    shown = authenticated_client.get("/email-insights/address").json()
    second = address_of(authenticated_client)

    assert first.endswith(f"@{DOMAIN}") and len(first.split("@")[0]) == 20
    assert shown["address"] == first and shown["enabled"] is True
    assert second != first
    assert authenticated_client.delete("/email-insights/address").status_code == 204
    assert authenticated_client.get("/email-insights/address").json()["enabled"] is False


def test_matched_rejection_becomes_a_pending_suggestion_without_changing_anything(authenticated_client, db_session):
    opportunity_id = create(authenticated_client, "Trendyol", status="Teknik mülakat")
    recipient = f"Ben <{address_of(authenticated_client)}>"

    response = deliver(authenticated_client, recipient, REJECTION)

    assert response.status_code == 202 and response.json() == {"status": "accepted"}
    [suggestion] = pending(authenticated_client)
    assert suggestion["opportunity"]["id"] == opportunity_id
    assert suggestion["email_type"] == "ret"
    assert suggestion["suggestion"]["status"] == "Reddedildi"
    assert suggestion["subject"] == "Başvurunuz hakkında"
    db_session.expire_all()
    assert db_session.get(Opportunity, opportunity_id).status == "Teknik mülakat"


def test_email_body_is_never_stored(authenticated_client, db_session):
    create(authenticated_client, "Trendyol")
    deliver(authenticated_client, address_of(authenticated_client), REJECTION)

    stored = db_session.query(EmailSuggestion).one()
    assert REJECTION not in " ".join(str(value) for value in vars(stored).values())


def test_applying_a_suggestion_updates_status_contact_and_task_once(authenticated_client, db_session):
    opportunity_id = create(authenticated_client, "Trendyol")
    deliver(authenticated_client, address_of(authenticated_client), ASSESSMENT, subject="Kodlama testi")
    [suggestion] = pending(authenticated_client)

    applied = authenticated_client.post(f"/email-insights/suggestions/{suggestion['id']}/apply")
    again = authenticated_client.post(f"/email-insights/suggestions/{suggestion['id']}/apply")

    assert applied.status_code == 200 and applied.json()["state"] == "applied"
    assert again.status_code == 409 and again.json()["error_code"] == "suggestion_not_pending"
    db_session.expire_all()
    assert db_session.get(Opportunity, opportunity_id).last_contact_date is not None
    [task] = db_session.query(Task).filter_by(opportunity_id=opportunity_id).all()
    assert task.description == "Trendyol değerlendirmesini (test/ödev) tamamla"
    assert pending(authenticated_client) == []


def test_dismissing_changes_nothing(authenticated_client, db_session):
    opportunity_id = create(authenticated_client, "Trendyol", status="Teknik mülakat")
    deliver(authenticated_client, address_of(authenticated_client), REJECTION)
    [suggestion] = pending(authenticated_client)

    response = authenticated_client.post(f"/email-insights/suggestions/{suggestion['id']}/dismiss")

    assert response.json()["state"] == "dismissed"
    db_session.expire_all()
    assert db_session.get(Opportunity, opportunity_id).status == "Teknik mülakat"
    assert pending(authenticated_client) == []


def test_unmatched_unrelated_and_duplicate_emails_leave_no_extra_trace(authenticated_client, db_session):
    create(authenticated_client, "Trendyol")
    recipient = address_of(authenticated_client)

    deliver(authenticated_client, recipient, REJECTION, sender="ik@bilinmeyensirket.com")
    deliver(authenticated_client, recipient, NEWSLETTER, sender="bulten@kariyer.net", subject="Yeni ilanlar")
    deliver(authenticated_client, recipient, REJECTION)
    deliver(authenticated_client, recipient, REJECTION)

    assert db_session.query(EmailSuggestion).count() == 1


def test_unknown_or_rotated_address_is_accepted_but_ignored(authenticated_client, db_session):
    create(authenticated_client, "Trendyol")
    old = address_of(authenticated_client)
    address_of(authenticated_client)

    unknown = deliver(authenticated_client, f"yok@{DOMAIN}", REJECTION)
    rotated = deliver(authenticated_client, old, REJECTION)

    assert unknown.status_code == rotated.status_code == 202
    assert db_session.query(EmailSuggestion).count() == 0


def test_gmail_forwarding_confirmation_code_is_shown_to_the_user(authenticated_client):
    recipient = address_of(authenticated_client)

    deliver(
        authenticated_client,
        recipient,
        "ali@gmail.com has requested to automatically forward mail to your email address.\nConfirmation code: 987654321",
        sender="Gmail Team <forwarding-noreply@google.com>",
        subject="(#987654321) Gmail Forwarding Confirmation - Receive Mail from ali@gmail.com",
    )

    shown = authenticated_client.get("/email-insights/address").json()
    assert shown["verification_code"] == "987654321"
    assert pending(authenticated_client) == []


def test_inbound_requires_the_shared_secret(authenticated_client, monkeypatch):
    recipient = address_of(authenticated_client)

    assert deliver(authenticated_client, recipient, REJECTION, secret="yanlis").status_code == 401
    assert deliver(authenticated_client, recipient, REJECTION, secret=None).status_code == 401
    monkeypatch.delenv("INBOUND_EMAIL_SECRET")
    assert deliver(authenticated_client, recipient, REJECTION).status_code == 503


def test_users_never_see_or_resolve_each_others_suggestions(authenticated_client):
    authenticated_client.post("/auth/register", json={"email": "other@example.com", "password": "OtherPass123"})
    other = {"Authorization": "Bearer " + authenticated_client.post(
        "/auth/token", data={"username": "other@example.com", "password": "OtherPass123"}
    ).json()["access_token"]}
    create(authenticated_client, "Trendyol", headers=other)
    deliver(authenticated_client, address_of(authenticated_client, headers=other), REJECTION)
    other_suggestion = authenticated_client.get("/email-insights/suggestions", headers=other).json()[0]["id"]

    assert pending(authenticated_client) == []
    assert authenticated_client.post(f"/email-insights/suggestions/{other_suggestion}/apply").status_code == 404
    assert authenticated_client.post(f"/email-insights/suggestions/{other_suggestion}/dismiss").status_code == 404


def test_assistant_mentions_the_latest_email_for_the_opportunity(authenticated_client):
    create(authenticated_client, "Trendyol", status="Teknik mülakat")
    deliver(authenticated_client, address_of(authenticated_client), REJECTION)

    answer = authenticated_client.post("/assistant/ask", json={"message": "Trendyol başvurum ne alemde"}).json()

    assert answer["intent"] == "basvuru_durumu"
    assert any(detail.startswith("Son e-posta (") and detail.endswith("olumsuz dönüş") for detail in answer["items"][0]["details"])


def test_suggestion_endpoints_require_authentication(client):
    assert client.get("/email-insights/suggestions").status_code == 401
    assert client.post("/email-insights/address").status_code == 401
