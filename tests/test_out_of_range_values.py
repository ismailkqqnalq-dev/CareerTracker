"""Sınır dışı sayı ve tarihler 500 yerine anlaşılır bir 422 dönmeli."""
import pytest


@pytest.mark.parametrize(
    "path",
    [
        "/opportunities/99999999999999999999",
        "/opportunities/99999999999999999999/detail",
        "/contacts/99999999999999999999",
        "/tasks/99999999999999999999",
    ],
)
def test_huge_record_id_is_rejected_instead_of_crashing(authenticated_client, path):
    response = authenticated_client.get(path)

    assert response.status_code == 422
    assert response.json()["error_code"] == "value_out_of_range"


def test_huge_id_in_request_body_is_rejected_instead_of_crashing(authenticated_client):
    response = authenticated_client.post(
        "/contacts", json={"name": "Ayşe", "opportunity_id": 10**20}
    )

    assert response.status_code == 422


@pytest.mark.parametrize("today", ["9999-12-31", "0001-01-01"])
def test_agenda_at_the_edge_of_the_calendar_does_not_crash(authenticated_client, today):
    response = authenticated_client.get(f"/agenda?today={today}")

    assert response.status_code in (200, 422)


def test_assistant_at_the_edge_of_the_calendar_does_not_crash(authenticated_client):
    response = authenticated_client.post(
        "/assistant/ask", json={"message": "bugün ne yapmalıyım", "today": "9999-12-31"}
    )

    assert response.status_code in (200, 422)
