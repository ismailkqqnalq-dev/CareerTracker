"""Şirket ve pozisyon zorunlu: boş, yalnızca boşluk ya da null kabul edilmez."""
import pytest

VALID = {"company": "Örnek AŞ", "position": "Backend"}


@pytest.mark.parametrize("field", ["company", "position"])
@pytest.mark.parametrize("value", ["", "   ", "\t\n"])
def test_create_rejects_blank_required_name(authenticated_client, field, value):
    response = authenticated_client.post("/opportunities", json={**VALID, field: value})

    assert response.status_code == 422


@pytest.mark.parametrize("field", ["company", "position"])
@pytest.mark.parametrize("value", ["", "   ", None])
def test_update_rejects_blank_or_null_required_name(authenticated_client, field, value):
    created = authenticated_client.post("/opportunities", json=VALID).json()

    response = authenticated_client.patch(f"/opportunities/{created['id']}", json={field: value})

    assert response.status_code == 422
    assert authenticated_client.get(f"/opportunities/{created['id']}").json()[field] == VALID[field]


def test_names_with_surrounding_spaces_are_kept_as_typed(authenticated_client):
    response = authenticated_client.post("/opportunities", json={"company": " Örnek AŞ ", "position": "Backend"})

    assert response.status_code in (200, 201)
    assert response.json()["company"] == " Örnek AŞ "


def test_update_without_names_still_works(authenticated_client):
    created = authenticated_client.post("/opportunities", json=VALID).json()

    response = authenticated_client.patch(f"/opportunities/{created['id']}", json={"status": "Mülakat"})

    assert response.status_code == 200
    assert response.json()["company"] == VALID["company"]
