from fastapi.testclient import TestClient
from app.main import app

def test_create_task():
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
    
    response = client.post("/tasks", json={
        "opportunity_id": opportunity_id,
        "description": "Takip e-postası gönder",
        "due_date": "2026-09-20",
        "is_completed": False})
    assert response.status_code == 200
    assert response.json()["description"] == "Takip e-postası gönder"
    
def test_get_all_tasks():
    client = TestClient(app)
    response = client.get("/tasks")
    assert response.status_code == 200
    assert len(response.json()) >= 1
    
def test_get_task_by_id():
    client = TestClient(app)
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
    create_response= client.post("/tasks", json={
        "opportunity_id": opportunity_id,
        "description": "Algoritma çalış",
        "due_date": "2026-09-21",
        "is_completed": False
    })
    task_id = create_response.json()["id"]
    
    response= client.get(f"/tasks/{task_id}")
    assert response.status_code == 200
    assert response.json()["id"] == task_id
    
def test_get_task_not_found():
    client = TestClient(app)
    response = client.get("/tasks/999999")
    assert response.status_code == 404

def test_update_task():
    client = TestClient(app)
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
    create_response = client.post("/tasks", json={
        "opportunity_id": opportunity_id,
        "description": "ilk görev",
        "due_date": "2026-09-22",
        "is_completed": False
    })
    task_id = create_response.json()["id"]
    
    update_response = client.patch(f"/tasks/{task_id}", json={
        
        "is_completed": True
    })
    assert update_response.status_code == 200
    assert update_response.json()["is_completed"] == True
    
def test_delete_task():
    client = TestClient(app)
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
    
    create_response = client.post("/tasks", json={
        "opportunity_id": opportunity_id,
        "description": "Silinecek görev",
        "due_date": "2026-09-23",
        "is_completed": False
    })
    task_id = create_response.json()["id"]
    
    delete_response = client.delete(f"/tasks/{task_id}")
    assert delete_response.status_code == 200