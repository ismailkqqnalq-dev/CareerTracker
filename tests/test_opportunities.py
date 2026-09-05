from fastapi.testclient import TestClient
from app.main import app
from app.schemas.opportunity import OpportunityCreate, OpportunityResponse, OpportunityUpdate
def test_create_opportunity():
    client = TestClient(app)
    response=client.post("/opportunities", json={
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
    assert response.status_code == 200
    assert response.json()["company"] == "Test Şirketi"

def test_opportunities():
    client = TestClient(app)
    response = client.get("/opportunities")
    assert response.status_code == 200
    assert len(response.json())>=1
    
def test_get_opportunity_by_id():
    client = TestClient(app)
    create_response = client.post("/opportunities", json={
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
    opportunity_id = create_response.json()["id"]
    response = client.get(f"/opportunities/{opportunity_id}")
    assert response.status_code == 200
    assert response.json()["id"] == opportunity_id

def test_get_opportunity_not_found():
    client = TestClient(app)
    response = client.get("/opportunities/999999")
    assert response.status_code == 404

def test_update_opportunity():
    client = TestClient(app)
    create_response = client.post("/opportunities", json={
        "company": "Test Şirketi1",
        "position": "Test Pozisyon1",
        "type": "staj",
        "application_date": "2026-09-05",
        "job_link": "https://example1.com",
        "salary": 20000,
        "location": "Ankara",
        "status": "Başvuruldu",
        "notes": "Test notu",
        "next_action": "Takip et",
        "last_contact_date": "2026-09-05"
    })
    
    opportunity_id = create_response.json()["id"]

    update_response = client.patch(f"/opportunities/{opportunity_id}",json={
        "company": "Güncellenmiş Test Şirketi"})
    assert update_response.status_code == 200
    assert update_response.json()["company"] ==("Güncellenmiş Test Şirketi")

def test_delete_opportunity():
    client = TestClient(app)
    create_response= client.post("/opportunities", json={
        "company": "Silinecek Şirket",
        "position": "Test Pozisyon",
        "type": "staj",
        "application_date": "2026-09-05",
        "job_link": "https://example3.com",
        "salary": 8000,
        "location": "Bursa",
        "status": "Başvuruldu",
        "notes": "Test notu",
        "next_action": "Takip et",
        "last_contact_date": "2026-09-05"
    })
    opportunity_id = create_response.json()["id"]
    delete_response = client.delete(f"/opportunities/{opportunity_id}") 
    assert delete_response.status_code==200