

def test_create_contact(authenticated_client):
    client = authenticated_client
     
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
    response = client.post("/contacts", json={
        "name": "Test Kişi",
        "role": "Test Rol",
        "email": "test@example.com",
        "linkedin": "https://linkedin.com/in/test",
        "opportunity_id": opportunity_id
    })
    assert response.status_code == 200
    assert response.json()["name"] == "Test Kişi"

def test_get_all_contacts(authenticated_client):
    client = authenticated_client
    response = client.get("/contacts")
    assert response.status_code == 200

def test_get_contact_by_id(authenticated_client):
    client= authenticated_client
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
    create_response = client.post("/contacts", json={
        "name": "Test Kişi2",
        "role": "Test Rol2",
        "email": "test2@example.com",
        "linkedin": "https://linkedin.com/in/test2",
        "opportunity_id": opportunity_id
    })
    contact_id = create_response.json()["id"]

    response = client.get(f"/contacts/{contact_id}")
    assert response.status_code == 200
    assert response.json()["id"] == contact_id
                                      
def test_get_contact_not_found(authenticated_client):
    client = authenticated_client
    response = client.get("/contacts/999999")
    assert response.status_code == 404

def test_update_contact(authenticated_client):
    client= authenticated_client
    opp_response = client.post("/opportunities", json={
           "company": "Test Şirketi3",
           "position": "Test Pozisyon3",
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
    create_response = client.post("/contacts", json={
           "name": "Test Kişi3",
           "role": "Test Rol3",
           "email": "test3@example.com",
           "linkedin": "https://linkedin.com/in/test3",
           "opportunity_id": opportunity_id
       })
    contact_id = create_response.json()["id"]
    update_response = client.patch(f"/contacts/{contact_id}", json={
        "role": "Güncellenmiş Rol"})
    assert update_response.status_code == 200
    assert update_response.json()["role"] == "Güncellenmiş Rol"
    
def test_delete_contact(authenticated_client):
    client= authenticated_client
    response = client.post("/opportunities", json={
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
    opportunity_id = response.json()["id"]
    create_response = client.post("/contacts", json={
               "name": "silinecek kişi",
               "role": "silinecek rol",
               "email": "silinecek@example.com",
               "linkedin": "https://linkedin.com/in/silinecek",
               "opportunity_id": opportunity_id
           })
    contact_id = create_response.json()["id"]
    delete_response = client.delete(f"/contacts/{contact_id}")
    assert delete_response.status_code == 200


def test_delete_contact_preserves_activity_and_clears_contact_link(authenticated_client):
    client = authenticated_client
    opportunity_id = client.post("/opportunities", json={
        "company": "Contact delete test",
        "position": "Engineer",
        "type": "full-time",
        "application_date": "2026-10-28",
        "job_link": "https://example.com/contact-delete",
        "salary": 1000,
        "location": "Remote",
        "status": "Başvuruldu",
        "notes": "test",
        "next_action": "follow up",
        "last_contact_date": "2026-10-28",
    }).json()["id"]
    contact_id = client.post("/contacts", json={
        "name": "Contact to delete",
        "role": "Recruiter",
        "email": "contact-delete@example.com",
        "linkedin": "https://example.com/person",
        "opportunity_id": opportunity_id,
    }).json()["id"]
    activity_id = client.post("/activities", json={
        "opportunity_id": opportunity_id,
        "contact_id": contact_id,
        "activity_type": "email",
        "dates": "2026-10-28",
        "notes": "Keep this activity after deleting its contact",
    }).json()["id"]

    response = client.delete(f"/contacts/{contact_id}")

    assert response.status_code == 200
    assert client.get(f"/contacts/{contact_id}").status_code == 404
    activity = client.get(f"/activities/{activity_id}")
    assert activity.status_code == 200
    assert activity.json()["contact_id"] is None
