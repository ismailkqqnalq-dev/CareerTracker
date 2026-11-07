import pytest


@pytest.mark.parametrize("path,status", [("/", 200), ("/auth/me", 401), ("/does-not-exist", 404), ("/docs", 200)])
def test_response_security_headers(client, path, status):
    response = client.get(path)
    assert response.status_code == status
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert response.headers["X-Frame-Options"] == "DENY"
    assert response.headers["Referrer-Policy"] == "no-referrer"


def test_authenticated_response_not_cached(authenticated_client):
    response = authenticated_client.get("/auth/me")
    assert response.status_code == 200
    assert response.headers["Cache-Control"] == "no-store"


def test_body_limit_response_has_security_headers(client):
    response = client.post("/auth/register", content=b"x", headers={"Content-Length": str(1024 * 1024 + 1)})
    assert response.status_code == 413
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert response.headers["Cache-Control"] == "no-store"
