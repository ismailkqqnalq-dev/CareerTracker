from app.schemas.opportunity import OpportunityCreate, OpportunityResponse, OpportunityUpdate

def test_create_opportunity(authenticated_client):
    client = authenticated_client
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

def test_opportunities(authenticated_client):
    client = authenticated_client
    response = client.get("/opportunities")
    assert response.status_code == 200
    assert response.json() == []
    
def test_get_opportunity_by_id(authenticated_client):
    client = authenticated_client
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

def test_get_opportunity_not_found(authenticated_client):
    client = authenticated_client
    response = client.get("/opportunities/999999")
    assert response.status_code == 404

def test_update_opportunity(authenticated_client):
    client = authenticated_client
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

def test_delete_opportunity(authenticated_client):
    client = authenticated_client
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


def test_delete_opportunity_cascades_linked_crm_records(authenticated_client):
    client = authenticated_client
    opportunity = client.post("/opportunities", json={
        "company": "Cascade test company",
        "position": "Engineer",
        "type": "full-time",
        "application_date": "2026-10-28",
        "job_link": "https://example.com/cascade",
        "salary": 1000,
        "location": "Remote",
        "status": "Başvuruldu",
        "notes": "test",
        "next_action": "follow up",
        "last_contact_date": "2026-10-28",
    }).json()
    contact = client.post("/contacts", json={
        "name": "Cascade test contact",
        "role": "Recruiter",
        "email": "cascade@example.com",
        "linkedin": "https://example.com/person",
        "opportunity_id": opportunity["id"],
    }).json()
    activity = client.post("/activities", json={
        "opportunity_id": opportunity["id"],
        "contact_id": contact["id"],
        "activity_type": "email",
        "dates": "2026-10-28",
        "notes": "test activity",
    }).json()
    task = client.post("/tasks", json={
        "opportunity_id": opportunity["id"],
        "description": "test task",
        "due_date": "2026-10-29",
        "is_completed": False,
    }).json()

    response = client.delete(f"/opportunities/{opportunity['id']}")

    assert response.status_code == 200
    assert client.get(f"/contacts/{contact['id']}").status_code == 404
    assert client.get(f"/activities/{activity['id']}").status_code == 404
    assert client.get(f"/tasks/{task['id']}").status_code == 404
