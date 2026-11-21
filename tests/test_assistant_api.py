"""POST /assistant/ask: niyete göre kayıtlardan üretilen cevaplar ve kullanıcı izolasyonu."""

TODAY = "2026-11-20"


def ask(client, message, headers=None):
    response = client.post("/assistant/ask", json={"message": message, "today": TODAY}, headers=headers)
    assert response.status_code == 200, response.text
    return response.json()


def create_opportunity(client, company, *, status="Başvuruldu", last_contact="2026-11-18",
                       next_action="", skill_ids=(), headers=None):
    response = client.post("/opportunities", headers=headers, json={
        "company": company, "position": "Backend", "type": "İş", "application_date": "2026-11-01",
        "job_link": "", "salary": 0, "location": "İzmir", "status": status, "notes": "",
        "next_action": next_action, "last_contact_date": last_contact, "skill_ids": list(skill_ids),
    })
    assert response.status_code == 200, response.text
    return response.json()["id"]


def create_task(client, opportunity_id, description, due_date):
    response = client.post("/tasks", json={
        "opportunity_id": opportunity_id, "description": description, "due_date": due_date,
    })
    assert response.status_code == 200, response.text


def create_skill(client, name):
    response = client.post("/skills", json={"name": name, "category": "tool"})
    assert response.status_code == 201, response.text
    return response.json()["id"]


def other_user_headers(client):
    credentials = {"email": "other@example.com", "password": "OtherPass123"}
    client.post("/auth/register", json=credentials)
    token = client.post(
        "/auth/token", data={"username": credentials["email"], "password": credentials["password"]}
    ).json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def test_reports_an_opportunity_named_with_a_turkish_suffix(authenticated_client):
    opportunity_id = create_opportunity(
        authenticated_client, "Trendyol", status="Teknik mülakat",
        last_contact="2026-11-08", next_action="Teşekkür e-postası",
    )
    create_task(authenticated_client, opportunity_id, "Mülakat hazırlığı", "2026-11-25")

    result = ask(authenticated_client, "Trendyol'daki başvurum ne alemde")

    assert result["intent"] == "basvuru_durumu"
    assert result["items"][0]["title"] == "Trendyol · Backend"
    assert result["items"][0]["details"] == [
        "Durum: Teknik mülakat",
        "Başvuru tarihi: 01.11.2026",
        "Son temas: 12 gün önce",
        "Sıradaki adım: Teşekkür e-postası",
        "Açık görev: Mülakat hazırlığı (son tarih 25.11.2026)",
    ]


def test_never_matches_another_users_opportunity(authenticated_client):
    headers = other_user_headers(authenticated_client)
    create_opportunity(authenticated_client, "Getir", headers=headers)
    create_opportunity(authenticated_client, "Aselsan")

    result = ask(authenticated_client, "Getir başvurum ne alemde")

    assert result["intent"] == "basvuru_durumu"
    assert result["items"] == []
    assert result["suggestions"] == ["Aselsan başvurum ne alemde?"]
    assert "Getir" not in str(result["items"]) + result["reply"]


def test_lists_overdue_today_and_upcoming_tasks(authenticated_client):
    opportunity_id = create_opportunity(authenticated_client, "Insider")
    create_task(authenticated_client, opportunity_id, "Portföyü güncelle", "2026-11-17")
    create_task(authenticated_client, opportunity_id, "İK'yı ara", TODAY)
    create_task(authenticated_client, opportunity_id, "Vaka çalışması", "2026-11-24")

    result = ask(authenticated_client, "Bugün ne yapmalıyım")

    assert result["intent"] == "bugun_ne_var"
    assert result["reply"] == "3 açık görevin var: 1 gecikmiş, 1 bugün, 1 bu hafta."
    assert [item["details"][0] for item in result["items"]] == ["Gecikti (17.11.2026)", "Bugün", "24.11.2026"]


def test_lists_stale_active_opportunities_but_not_offers(authenticated_client):
    create_opportunity(authenticated_client, "Sessiz AŞ", last_contact="2026-11-05", next_action="İK'ya yaz")
    create_opportunity(authenticated_client, "Teklif AŞ", status="Teklif", last_contact="2026-10-01")

    result = ask(authenticated_client, "Kimden ses çıkmadı")

    assert result["intent"] == "takip_gereken"
    assert [item["title"] for item in result["items"]] == ["Sessiz AŞ · Backend"]
    assert result["items"][0]["details"] == ["Durum: Başvuruldu", "15 gündür temas yok", "Sıradaki adım: İK'ya yaz"]


def test_ranks_skills_missing_from_the_profile_by_demand(authenticated_client):
    docker, python, kafka = (create_skill(authenticated_client, name) for name in ("Dockerx", "Pythonx", "Kafkax"))
    create_opportunity(authenticated_client, "Birinci", skill_ids=[docker, python])
    create_opportunity(authenticated_client, "İkinci", skill_ids=[docker, kafka])
    assert authenticated_client.post("/users/me/skills", json={"skill_id": python}).status_code in (200, 201)

    result = ask(authenticated_client, "Hangi becerileri geliştirmeliyim")

    assert result["intent"] == "beceri_acigi"
    assert result["items"] == [
        {"title": "Dockerx", "details": ["2 / 2 başvuruda isteniyor"]},
        {"title": "Kafkax", "details": ["1 / 2 başvuruda isteniyor"]},
    ]
    assert "eğilim" in result["reply"]


def test_explains_when_no_opportunity_has_skills(authenticated_client):
    create_opportunity(authenticated_client, "Becerisiz AŞ")

    result = ask(authenticated_client, "Eksik becerilerim neler")

    assert result["intent"] == "beceri_acigi"
    assert result["items"] == []
    assert "henüz kayıtlı beceri yok" in result["reply"]


def test_summarizes_counts_by_status(authenticated_client):
    create_opportunity(authenticated_client, "A1", status="Başvuruldu")
    create_opportunity(authenticated_client, "A2", status="Teknik mülakat")
    create_opportunity(authenticated_client, "A3", status="Reddedildi")

    result = ask(authenticated_client, "Kaç başvurum var")

    assert result["intent"] == "genel_durum"
    assert result["reply"].startswith("Toplam 3 başvurun var: 2 tanesi hâlâ süreçte")


def test_off_topic_question_gets_example_questions_instead_of_data(authenticated_client):
    create_opportunity(authenticated_client, "Gizli AŞ")

    result = ask(authenticated_client, "Bana bir fıkra anlat")

    assert result["intent"] == "anlasilamadi"
    assert result["items"] == []
    assert "Bugün ne yapmalıyım?" in result["suggestions"]


def test_reply_is_not_cached(authenticated_client):
    response = authenticated_client.post("/assistant/ask", json={"message": "Merhaba"})

    assert response.status_code == 200
    assert response.headers["Cache-Control"] == "no-store"
    assert response.json()["intent"] == "yardim"


def test_rejects_blank_too_long_and_unknown_fields(authenticated_client):
    for body in ({"message": "   "}, {"message": "a" * 501}, {"message": "Merhaba", "extra": 1}):
        assert authenticated_client.post("/assistant/ask", json=body).status_code == 422


def test_requires_authentication(client):
    assert client.post("/assistant/ask", json={"message": "Merhaba"}).status_code == 401
