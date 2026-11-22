"""GET /opportunities?q=&status=: tüm kayıtlarda sunucu tarafı arama, Türkçe harf katlama ve durum filtresi."""


def create(client, company, *, position="Backend", location="İzmir", status="Başvuruldu",
           next_action="", notes="", headers=None):
    response = client.post("/opportunities", headers=headers, json={
        "company": company, "position": position, "type": "İş", "application_date": "2026-11-01",
        "job_link": "", "salary": 0, "location": location, "status": status, "notes": notes,
        "next_action": next_action, "last_contact_date": "2026-11-10",
    })
    assert response.status_code == 200, response.text
    return response.json()["id"]


def search(client, **params):
    response = client.get("/opportunities", params=params)
    assert response.status_code == 200, response.text
    return [item["company"] for item in response.json()], int(response.headers["X-Total-Count"])


def test_search_finds_records_beyond_the_first_page(authenticated_client):
    for index in range(55):
        create(authenticated_client, f"Doldurma {index}")
    create(authenticated_client, "Hedef Teknoloji")

    companies, total = search(authenticated_client, q="hedef")

    assert companies == ["Hedef Teknoloji"]
    assert total == 1


def test_search_folds_turkish_letters_and_case(authenticated_client):
    create(authenticated_client, "Şeker Yazılım", location="İstanbul")
    create(authenticated_client, "Diğer", location="Ankara")

    assert search(authenticated_client, q="seker")[0] == ["Şeker Yazılım"]
    assert search(authenticated_client, q="ŞEKER")[0] == ["Şeker Yazılım"]
    assert search(authenticated_client, q="istanbul")[0] == ["Şeker Yazılım"]
    assert search(authenticated_client, q="İSTANBUL")[0] == ["Şeker Yazılım"]


def test_search_covers_position_next_action_and_notes(authenticated_client):
    create(authenticated_client, "Pozisyonlu", position="Gömülü Yazılım Mühendisi")
    create(authenticated_client, "Adımlı", next_action="Teşekkür e-postası gönder")
    create(authenticated_client, "Notlu", notes="İK ile maaş konuşuldu")
    create(authenticated_client, "Alakasız")

    assert search(authenticated_client, q="gomulu")[0] == ["Pozisyonlu"]
    assert search(authenticated_client, q="teşekkür")[0] == ["Adımlı"]
    assert search(authenticated_client, q="maas")[0] == ["Notlu"]


def test_status_filter_is_case_insensitive_and_combines_with_search(authenticated_client):
    create(authenticated_client, "Alfa", status="Teknik mülakat")
    create(authenticated_client, "Beta", status="teknik MÜLAKAT")
    create(authenticated_client, "Alfa İkinci", status="Teklif")

    assert sorted(search(authenticated_client, status="Teknik mülakat")[0]) == ["Alfa", "Beta"]
    assert search(authenticated_client, status="Teknik mülakat", q="alfa") == (["Alfa"], 1)


def test_filtered_results_are_paginated_with_the_filtered_total(authenticated_client):
    for index in range(5):
        create(authenticated_client, f"Teklifli {index}", status="Teklif")
    create(authenticated_client, "Başka", status="Başvuruldu")

    companies, total = search(authenticated_client, status="Teklif", limit=2, offset=2)

    assert total == 5
    assert companies == ["Teklifli 2", "Teklifli 3"]


def test_like_wildcards_in_the_query_are_literal(authenticated_client):
    create(authenticated_client, "Yüzde %100 AŞ")
    create(authenticated_client, "Sıradan AŞ")

    assert search(authenticated_client, q="%")[0] == ["Yüzde %100 AŞ"]
    assert search(authenticated_client, q="_")[0] == []


def test_blank_filters_return_everything(authenticated_client):
    create(authenticated_client, "Bir")
    create(authenticated_client, "İki")

    assert search(authenticated_client, q="   ", status="")[1] == 2


def test_search_never_returns_another_users_records(authenticated_client):
    authenticated_client.post("/auth/register", json={"email": "other@example.com", "password": "OtherPass123"})
    token = authenticated_client.post(
        "/auth/token", data={"username": "other@example.com", "password": "OtherPass123"}
    ).json()["access_token"]
    create(authenticated_client, "Gizli Ortak", headers={"Authorization": f"Bearer {token}"})
    create(authenticated_client, "Benim Ortak")

    assert search(authenticated_client, q="ortak") == (["Benim Ortak"], 1)


def test_rejects_overlong_filters(authenticated_client):
    assert authenticated_client.get("/opportunities", params={"q": "a" * 201}).status_code == 422
    assert authenticated_client.get("/opportunities", params={"status": "a" * 51}).status_code == 422
