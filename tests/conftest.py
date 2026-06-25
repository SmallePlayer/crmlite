import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.database import Base, get_db
from app.main import app
from app.models import User, Role
from app.auth import hash_password

TEST_DATABASE_URL = "sqlite:///./test.db"

engine = create_engine(TEST_DATABASE_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(bind=engine, autoflush=False)


@pytest.fixture(autouse=True)
def setup_db():
    Base.metadata.create_all(bind=engine)
    db = TestingSessionLocal()
    role = Role(
        name="admin",
        can_view_clients=True, can_edit_clients=True,
        can_view_services=True, can_edit_services=True,
        can_view_orders=True, can_edit_orders=True,
        can_delete_orders=True, can_manage_users=True,
        can_view_reports=True, can_edit_reports=True,
        can_view_warehouse=True, can_edit_warehouse=True,
        can_assign_tasks=True,
    )
    db.add(role)
    db.commit()
    db.refresh(role)
    if not db.query(User).filter(User.username == "testadmin").first():
        db.add(User(
            username="testadmin",
            hashed_password=hash_password("test123"),
            role_id=role.id,
            full_name="Test Admin",
        ))
        db.commit()
    yield
    Base.metadata.drop_all(bind=engine)
    db.close()


def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = override_get_db


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


@pytest.fixture
def token(client):
    r = client.post("/api/auth/login", json={"username": "testadmin", "password": "test123"})
    return r.json()["token"]


@pytest.fixture
def auth_headers(token):
    return {"Authorization": f"Bearer {token}"}
