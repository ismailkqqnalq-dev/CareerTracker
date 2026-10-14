from sqlalchemy import StaticPool, create_engine
from sqlalchemy.orm import sessionmaker
import os
import secrets

# Ephemeral test-only key; never use the application's real secret in tests.
os.environ["JWT_SECRET_KEY"] = secrets.token_hex(32)
from app.database.session import Base, get_db
import pytest
from app.main import app
from fastapi.testclient import TestClient

database_url = "sqlite:///:memory:"

engine = create_engine(database_url, connect_args={"check_same_thread": False},  poolclass=StaticPool)

TestingSessionLocal = sessionmaker(
    bind=engine,
    autoflush=False,
    expire_on_commit=False
)

@pytest.fixture()
def client():
    Base.metadata.create_all(bind=engine)
    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()
    app.dependency_overrides[get_db] = override_get_db
    test_client = TestClient(app)
    yield test_client
    app.dependency_overrides.clear()
    Base.metadata.drop_all(bind=engine)
    
@pytest.fixture()
def authenticated_client(client):
    client.post(
        "/auth/register",
        json={
            "email": "owner@example.com",
            "password": "StrongPass123",
        }
    )

    login_response = client.post(
        "/auth/token",
        data={
            "username": "owner@example.com",
            "password": "StrongPass123",
        },
    )
    assert login_response.status_code == 200

    token = login_response.json()["access_token"]
    client.headers.update({"Authorization": f"Bearer {token}"})
    return client
