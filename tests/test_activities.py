from fastapi.testclient import TestClient
from app.main import app

def test_create_activity():
    client = TestClient(app)

    opp_response = client.post("/opportunities", json={
        "company": "Test Şirketi",
        "position": "Test Pozisyon",
        "type": "staj",
        "application_date": "2026-09-04",
        "job_link": "https://example.com",
        "salary": 10000,
        "location": "İstanbul",
        "status": "Başvuruldu",
        "notes": "Test notu",
        "next_action": "Takip et",
        "last_contact_date": "2026-09-04"
    })
    opportunity_id = opp_response.json()["id"]

    response = client.post("/activities", json={
        "opportunity_id": opportunity_id,
        "contact_id": None,
        "activity_type": "Telefon görüşmesi",
        "dates": "2026-09-13",
        "notes": "İlk görüşme"
    })
    assert response.status_code == 200
    assert response.json()["activity_type"] == "Telefon görüşmesi"
    
def test_get_all_activities():
    client= TestClient(app)
    response = client.get("/activities")
    assert response.status_code == 200
    assert len(response.json()) >= 1  
    
def test_get_activity_by_id():
    client= TestClient(app)
    opp_response = client.post("/opportunities", json={
        "company": "Test Şirketi2",
        "position": "Test Pozisyon2",
        "type": "staj",
        "application_date": "2026-09-05",
        "job_link": "https://example2.com",
        "salary": 12000,
        "location": "İzmir",
        "status": "Başvuruldu",
        "notes": "Test notu",
        "next_action": "Takip et",
        "last_contact_date": "2026-09-05"
    })
    opportunity_id = opp_response.json()["id"]
    create_response = client.post("/activities", json={
        "opportunity_id": opportunity_id,
        "contact_id": None,
        "activity_type": "E-posta gönderimi",
        "dates": "2026-09-14",
        "notes": "İkinci görüşme"
    })
    activity_id = create_response.json()["id"]
    response = client.get(f"/activities/{activity_id}")
    assert response.status_code == 200
    assert response.json()["id"] == activity_id
    
def test_get_activity_not_found():
    client= TestClient(app)
    response = client.get("/activities/9999999")
    assert response.status_code == 404

def test_update_activity():
    client= TestClient(app)
    opp_response = client.post("/opportunities", json={
        "company": "Test Şirketi3",
        "position": "Test Pozisyon3",
        "type": "staj",
        "application_date": "2026-09-06",
        "job_link": "https://example3.com",
        "salary": 15000,
        "location": "Ankara",
        "status": "Başvuruldu",
        "notes": "Test notu",
        "next_action": "Takip et",
        "last_contact_date": "2026-09-06"
    })
    opportunity_id = opp_response.json()["id"]
    create_response = client.post("/activities", json={
        "opportunity_id": opportunity_id,
        "contact_id": None,
        "activity_type": "Yüz yüze görüşme",
        "dates": "2026-09-15",
        "notes": "Üçüncü görüşme"
    })
    activity_id = create_response.json()["id"]
    response = client.patch(f"/activities/{activity_id}", json={
        
        "notes": "Güncellenmiş not"
    })
    assert response.status_code == 200
    assert response.json()["notes"] == "Güncellenmiş not"

def test_delete_activity():
    client= TestClient(app)
    opp_response = client.post("/opportunities", json={
        "company": "Silinecek Şirket",
        "position": "Test Pozisyon",
        "type": "staj",
        "application_date": "2026-09-05",
        "job_link": "https://example4.com",
        "salary": 9000,
        "location": "Bursa",
        "status": "Başvuruldu",
        "notes": "Test notu",
        "next_action": "Takip et",
        "last_contact_date": "2026-09-05"
    })
    opportunity_id = opp_response.json()["id"]
    create_response = client.post("/activities", json={
        "opportunity_id": opportunity_id,
        "contact_id": None,
        "activity_type": "Toplantı",
        "dates": "2026-09-17",
        "notes": "silinecek aktivite"
    })
    activity_id = create_response.json()["id"]
    response = client.delete(f"/activities/{activity_id}")
    assert response.status_code == 200
    