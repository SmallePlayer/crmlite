import pytest
import os
import tempfile
from pathlib import Path
from fastapi.testclient import TestClient

os.environ["DATABASE_URL"] = f"sqlite:///{tempfile.mktemp(suffix='.db')}"
os.environ["SECRET_KEY"] = "test-secret-key-for-testing-only"

from main import app
from database import engine, Base


@pytest.fixture(autouse=True)
def setup_db():
    Base.metadata.create_all(bind=engine)
    from helpers import _seed_data
    _seed_data()
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def client():
    return TestClient(app)


def test_health_check(client):
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["database"] == "connected"


def test_login_page(client):
    response = client.get("/login")
    assert response.status_code == 200
    assert "CRM" in response.text


def test_login_invalid_credentials(client):
    response = client.post("/login", data={
        "username": "invalid_user",
        "password": "invalid_pass"
    })
    assert response.status_code == 401


def test_redirect_to_login(client):
    response = client.get("/", follow_redirects=False)
    assert response.status_code == 303
    assert response.headers["location"] == "/login"


def test_static_files(client):
    response = client.get("/static/manifest.json")
    assert response.status_code == 200


def test_login_rate_limiting(client):
    for i in range(6):
        response = client.post("/login", data={
            "username": "bad_user",
            "password": "bad_pass"
        })
    assert response.status_code == 429


def test_login_success_with_seed_data(client):
    from routers.auth import _login_attempts
    _login_attempts.clear()
    response = client.post("/login", data={
        "username": "admin",
        "password": "admin"
    }, follow_redirects=False)
    assert response.status_code == 303
    assert "token" in response.cookies
