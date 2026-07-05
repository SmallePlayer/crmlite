import pytest
from fastapi.testclient import TestClient
from main import app


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
