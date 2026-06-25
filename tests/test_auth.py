def test_login_success(client):
    r = client.post("/api/auth/login", json={"username": "testadmin", "password": "test123"})
    assert r.status_code == 200
    data = r.json()
    assert "token" in data
    assert data["user"]["username"] == "testadmin"


def test_login_failure(client):
    r = client.post("/api/auth/login", json={"username": "testadmin", "password": "wrong"})
    assert r.status_code == 401


def test_me_unauthorized(client):
    r = client.get("/api/auth/me")
    assert r.status_code == 401


def test_me_authorized(client, auth_headers):
    r = client.get("/api/auth/me", headers=auth_headers)
    assert r.status_code == 200
    assert r.json()["username"] == "testadmin"
