from sqlalchemy import StaticPool, create_engine
from sqlalchemy.orm import sessionmaker
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