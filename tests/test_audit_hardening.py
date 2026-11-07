import csv
import io

import pytest

from app.database.session import get_db
from app.main import app
from app.models.activities import Activity
from app.models.contacts import Contact
from app.models.opportunity import Opportunity
from app.models.tasks import Task
from app.schemas.opportunity import OpportunityResponse, OpportunityUpdate
from app.schemas.skills import SkillResponse


def _opportunity_payload(**overrides):
    return {
        "company": "Audit Company",
        "position": "Software Engineer",
        "type": "staj",
        "application_date": "2026-11-04",
        "job_link": "https://example.test/job",
        "salary": 10000,
        "location": "İstanbul",
        "status": "Başvuruldu",
        "notes": "test note",
        "next_action": "follow up",
        "last_contact_date": "2026-11-04",
        **overrides,
    }


def test_opportunity_patch_defaults_are_none_not_tuples():
    patch = OpportunityUpdate()

    assert patch.model_dump() == {
        "company": None,
        "position": None,
        "type": None,
        "application_date": None,
        "job_link": None,
        "salary": None,
        "location": None,
        "status": None,
        "notes": None,
        "next_action": None,
        "last_contact_date": None,
    }


def test_response_schemas_do_not_reject_legacy_long_values():
    old_value = "x" * 2050
    opportunity = OpportunityResponse(
        id=1,
        company=old_value,
        position=None,
        type=None,
        application_date=None,
        job_link=old_value,
        salary=None,
        location=None,
        status=None,
        notes=None,
        next_action=None,
        last_contact_date=None,
    )
    skill = SkillResponse(id=1, name=old_value, category=None)

    assert opportunity.company == old_value
    assert skill.name == old_value


@pytest.mark.parametrize(
    "value",
    [
        "javascript:alert(1)",
        "data:text/html,x",
        "vbscript:alert(1)",
        "https://bad url.test",
        "https://example.test/\u0080path",
    ],
)
def test_opportunity_rejects_unsafe_job_link(authenticated_client, value):
    response = authenticated_client.post(
        "/opportunities",
        json=_opportunity_payload(job_link=value),
    )
    assert response.status_code == 422


def test_opportunity_accepts_uppercase_http_scheme(authenticated_client):
    response = authenticated_client.post(
        "/opportunities",
        json=_opportunity_payload(job_link="HTTP://example.test/job"),
    )
    assert response.status_code == 200


def test_opportunity_input_length_is_limited(authenticated_client):
    response = authenticated_client.post(
        "/opportunities",
        json=_opportunity_payload(company="x" * 201),
    )
    assert response.status_code == 422


def test_opportunity_rejects_too_long_url_and_notes(authenticated_client):
    too_long_url = authenticated_client.post(
        "/opportunities",
        json=_opportunity_payload(job_link="https://example.test/" + "x" * 2048),
    )
    too_long_notes = authenticated_client.post(
        "/opportunities",
        json=_opportunity_payload(notes="x" * 5001),
    )
    assert too_long_url.status_code == 422
    assert too_long_notes.status_code == 422


def test_opportunity_salary_must_fit_database_integer(authenticated_client):
    negative = authenticated_client.post(
        "/opportunities", json=_opportunity_payload(salary=-1)
    )
    overflow = authenticated_client.post(
        "/opportunities", json=_opportunity_payload(salary=2_147_483_648)
    )
    assert negative.status_code == 422
    assert overflow.status_code == 422


def test_contact_linkedin_accepts_http_and_rejects_unsafe_schemes(authenticated_client):
    client = authenticated_client
    opportunity_id = client.post(
        "/opportunities", json=_opportunity_payload()
    ).json()["id"]
    base = {
        "name": "Contact",
        "role": "Recruiter",
        "email": "contact@example.test",
        "opportunity_id": opportunity_id,
    }
    accepted = client.post("/contacts", json={**base, "linkedin": "HTTP://example.test/profile"})
    rejected = client.post("/contacts", json={**base, "linkedin": "javascript:alert(1)"})
    whitespace = client.post("/contacts", json={**base, "linkedin": "https://example.test/ bad"})

    assert accepted.status_code == 200
    assert rejected.status_code == 422
    assert whitespace.status_code == 422


def test_skill_and_alias_names_have_a_bounded_write_length(authenticated_client):
    client = authenticated_client
    oversized_skill = client.post(
        "/skills", json={"name": "x" * 121, "category": "tool"}
    )
    valid_skill = client.post(
        "/skills", json={"name": "Bounded skill", "category": "tool"}
    )
    assert oversized_skill.status_code == 422
    assert valid_skill.status_code == 201

    oversized_alias = client.post(
        f"/skills/{valid_skill.json()['id']}/aliases",
        json={"alias": "x" * 121},
    )
    assert oversized_alias.status_code == 422


def test_dashboard_status_metrics_ignore_case_and_surrounding_whitespace(authenticated_client):
    client = authenticated_client
    for status in ("  ön görüşme ", "TEKLİF", " REDDEDİLDİ "):
        response = client.post(
            "/opportunities",
            json=_opportunity_payload(status=status),
        )
        assert response.status_code == 200

    dashboard = client.get("/dashboard")

    assert dashboard.status_code == 200
    assert dashboard.json()["interview_count"] == 1
    assert dashboard.json()["offer_count"] == 1
    assert dashboard.json()["rejection_rate"] == pytest.approx(100 / 3, abs=0.01)


def test_opportunities_support_stable_pagination_and_total_count(authenticated_client):
    client = authenticated_client
    ids = []
    for company in ("First", "Second", "Third"):
        created = client.post(
            "/opportunities",
            json=_opportunity_payload(company=company),
        )
        assert created.status_code == 200
        ids.append(created.json()["id"])

    response = client.get("/opportunities?limit=1&offset=1")

    assert response.status_code == 200
    assert [row["id"] for row in response.json()] == [ids[1]]
    assert response.headers["X-Total-Count"] == "3"


def test_pagination_bounds_are_validated(authenticated_client):
    too_many = authenticated_client.get("/opportunities?limit=201")
    negative_offset = authenticated_client.get("/opportunities?offset=-1")
    assert too_many.status_code == 422
    assert negative_offset.status_code == 422


def test_csv_export_escapes_formula_cells_and_preserves_csv_format(authenticated_client):
    client = authenticated_client
    unsafe_values = [
        "=1+1",
        "  +SUM(A1:A2)",
        "\t@HYPERLINK",
        "\tplain text",
        "-cmd",
    ]
    for index, value in enumerate(unsafe_values):
        created = client.post(
            "/opportunities",
            json=_opportunity_payload(
                company=value,
                position=f"Engineer, {index}\nTürkçe",
            ),
        )
        assert created.status_code == 200

    response = client.get("/opportunities/export")

    assert response.status_code == 200
    rows = list(csv.reader(io.StringIO(response.content.decode("utf-8-sig"))))
    assert rows[0][0] == "id"
    assert [row[1] for row in rows[1:]] == [f"'{value}" for value in unsafe_values]
    assert rows[1][2] == "Engineer, 0\nTürkçe"


def test_csv_export_streams_large_user_list(authenticated_client):
    client = authenticated_client
    for index in range(205):
        response = client.post(
            "/opportunities",
            json=_opportunity_payload(company=f"Company {index}"),
        )
        assert response.status_code == 200

    exported = client.get("/opportunities/export")

    assert exported.status_code == 200
    rows = list(csv.reader(io.StringIO(exported.content.decode("utf-8-sig"))))
    assert len(rows) == 206
    assert rows[1][1] == "Company 0"
    assert rows[-1][1] == "Company 204"


def test_legacy_nullable_crm_fields_remain_serializable(authenticated_client):
    client = authenticated_client
    user_id = client.get("/auth/me").json()["id"]
    db_generator = app.dependency_overrides[get_db]()
    db = next(db_generator)
    try:
        opportunity = Opportunity(user_id=user_id)
        db.add(opportunity)
        db.flush()
        contact = Contact(user_id=user_id, opportunity_id=opportunity.id)
        task = Task(user_id=user_id, opportunity_id=opportunity.id)
        activity = Activity(user_id=user_id, opportunity_id=opportunity.id)
        db.add_all([contact, task, activity])
        db.commit()
        ids = (opportunity.id, contact.id, task.id, activity.id)
    finally:
        db_generator.close()

    paths = (
        f"/opportunities/{ids[0]}",
        f"/contacts/{ids[1]}",
        f"/tasks/{ids[2]}",
        f"/activities/{ids[3]}",
    )
    for path in paths:
        response = client.get(path)
        assert response.status_code == 200, (path, response.text)


def test_all_list_endpoints_page_with_consistent_count_and_order(authenticated_client):
    client = authenticated_client
    opportunities = []
    contacts = []
    tasks = []
    activities = []
    for index in range(2):
        opportunity = client.post(
            "/opportunities",
            json=_opportunity_payload(company=f"Page {index}"),
        ).json()
        opportunities.append(opportunity)
        contacts.append(client.post("/contacts", json={
            "name": f"Contact {index}", "role": "Recruiter",
            "email": f"contact{index}@example.test", "linkedin": "",
            "opportunity_id": opportunity["id"],
        }).json())
        tasks.append(client.post("/tasks", json={
            "opportunity_id": opportunity["id"], "description": f"Task {index}",
            "due_date": "2026-11-05", "is_completed": False,
        }).json())
        activities.append(client.post("/activities", json={
            "opportunity_id": opportunity["id"], "activity_type": "email",
            "dates": "2026-11-04", "notes": f"Activity {index}",
        }).json())

    expected = {
        "/opportunities": opportunities,
        "/contacts": contacts,
        "/tasks": tasks,
        "/activities": activities,
    }
    for path, rows in expected.items():
        response = client.get(f"{path}?limit=1&offset=1")
        assert response.status_code == 200, (path, response.text)
        assert [item["id"] for item in response.json()] == [rows[1]["id"]]
        assert response.headers["X-Total-Count"] == "2"


def test_skill_lists_and_suggestions_support_pagination(authenticated_client):
    client = authenticated_client
    skill_ids = []
    for name in ("Audit Skill A", "Audit Skill B"):
        created = client.post("/skills", json={"name": name, "category": "tool"})
        assert created.status_code == 201
        skill_ids.append(created.json()["id"])
    for raw_name in ("Unknown Audit A", "Unknown Audit B"):
        assert client.post("/skills/suggestions", json={"skill": raw_name}).status_code == 201

    opportunity_id = client.post("/opportunities", json=_opportunity_payload()).json()["id"]
    for name in ("Audit Skill A", "Audit Skill B"):
        assert client.post(
            f"/opportunities/{opportunity_id}/skills", json={"skill": name}
        ).status_code == 201
    for skill_id in skill_ids:
        assert client.post("/users/me/skills", json={"skill_id": skill_id}).status_code == 201

    checks = (
        ("/skills", 2),
        ("/skills/suggestions?status=pending", 2),
        ("/users/me/skills", 2),
        (f"/opportunities/{opportunity_id}/skills", 2),
    )
    for path, total in checks:
        response = client.get(f"{path}&limit=1&offset=1" if "?" in path else f"{path}?limit=1&offset=1")
        assert response.status_code == 200, (path, response.text)
        assert len(response.json()) == 1
        assert response.headers["X-Total-Count"] == str(total)


def test_opportunity_quota_is_per_user_and_returns_error_code(
    authenticated_client, monkeypatch
):
    client = authenticated_client
    monkeypatch.setenv("MAX_OPPORTUNITIES_PER_USER", "1")

    first = client.post("/opportunities", json=_opportunity_payload(company="Owner"))
    over_limit = client.post(
        "/opportunities", json=_opportunity_payload(company="Owner extra")
    )

    assert first.status_code == 200
    assert over_limit.status_code == 409
    assert over_limit.json()["error_code"] == "quota_exceeded"

    registration = client.post(
        "/auth/register",
        json={"email": "second-owner@example.com", "password": "StrongPass123"},
    )
    assert registration.status_code == 201
    login = client.post(
        "/auth/token",
        data={"username": "second-owner@example.com", "password": "StrongPass123"},
    )
    assert login.status_code == 200
    client.headers["Authorization"] = f"Bearer {login.json()['access_token']}"

    other_user_opportunity = client.post(
        "/opportunities", json=_opportunity_payload(company="Other owner")
    )

    assert other_user_opportunity.status_code == 200


def test_opportunity_quota_defaults_to_five_thousand(monkeypatch):
    from app.record_limits import get_max_opportunities_per_user

    monkeypatch.delenv("MAX_OPPORTUNITIES_PER_USER", raising=False)

    assert get_max_opportunities_per_user() == 5000
