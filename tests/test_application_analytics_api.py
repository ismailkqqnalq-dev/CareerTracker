from datetime import date


def _shift_month(value: date, offset: int) -> date:
    month_index = value.year * 12 + value.month - 1 + offset
    year, month_zero_based = divmod(month_index, 12)
    return date(year, month_zero_based + 1, 1)


def _create_opportunity(client, application_date: str):
    response = client.post(
        "/opportunities",
        json={
            "company": "Analytics test",
            "position": "Data analyst",
            "type": "full-time",
            "application_date": application_date,
            "job_link": "https://example.com/job",
            "salary": 1000,
            "location": "Remote",
            "status": "Başvuruldu",
            "notes": "",
            "next_action": "",
            "last_contact_date": application_date,
        },
    )
    assert response.status_code == 200
    return response.json()


def test_application_analytics_returns_zero_filled_monthly_counts(authenticated_client):
    client = authenticated_client
    current_month = date.today().replace(day=1)
    previous_month = _shift_month(current_month, -1)
    outside_period = _shift_month(current_month, -3)

    _create_opportunity(client, current_month.isoformat())
    _create_opportunity(client, previous_month.isoformat())
    _create_opportunity(client, previous_month.replace(day=15).isoformat())
    _create_opportunity(client, outside_period.isoformat())

    response = client.get("/analytics/applications", params={"months": 3})

    assert response.status_code == 200
    assert response.json() == {
        "months": 3,
        "start_month": _shift_month(current_month, -2).strftime("%Y-%m"),
        "end_month": current_month.strftime("%Y-%m"),
        "total_applications": 3,
        "applications_by_month": [
            {"month": _shift_month(current_month, -2).strftime("%Y-%m"), "count": 0},
            {"month": previous_month.strftime("%Y-%m"), "count": 2},
            {"month": current_month.strftime("%Y-%m"), "count": 1},
        ],
    }


def test_application_analytics_is_scoped_to_authenticated_user(
    authenticated_client,
):
    client = authenticated_client
    current_month = date.today().replace(day=1)
    _create_opportunity(client, current_month.isoformat())

    registration = client.post(
        "/auth/register",
        json={"email": "analytics-other@example.com", "password": "StrongPass123"},
    )
    assert registration.status_code == 201
    login = client.post(
        "/auth/token",
        data={"username": "analytics-other@example.com", "password": "StrongPass123"},
    )
    assert login.status_code == 200

    response = client.get(
        "/analytics/applications",
        params={"months": 2},
        headers={"Authorization": f"Bearer {login.json()['access_token']}"},
    )

    assert response.status_code == 200
    assert response.json()["total_applications"] == 0
    assert [row["count"] for row in response.json()["applications_by_month"]] == [0, 0]


def test_application_analytics_requires_authentication(client):
    response = client.get("/analytics/applications")

    assert response.status_code == 401


def test_application_analytics_months_must_be_between_one_and_sixty(
    authenticated_client,
):
    for months in (0, 61):
        response = authenticated_client.get(
            "/analytics/applications",
            params={"months": months},
        )
        assert response.status_code == 422
