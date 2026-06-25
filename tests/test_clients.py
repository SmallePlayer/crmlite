def test_list_clients(client, auth_headers):
    r = client.get("/api/clients", headers=auth_headers)
    assert r.status_code == 200
    assert r.json() == []


def test_create_client(client, auth_headers):
    r = client.post("/api/clients", json={"full_name": "Иван", "phone": "+7-999-123-45-67"}, headers=auth_headers)
    assert r.status_code == 200
    data = r.json()
    assert data["full_name"] == "Иван"
    assert data["phone"] == "+7-999-123-45-67"
    assert "id" in data


def test_get_client(client, auth_headers):
    r = client.post("/api/clients", json={"full_name": "Петр", "phone": "+7-999-111-22-33"}, headers=auth_headers)
    cid = r.json()["id"]
    r = client.get(f"/api/clients/{cid}", headers=auth_headers)
    assert r.status_code == 200
    assert r.json()["full_name"] == "Петр"


def test_delete_client(client, auth_headers):
    r = client.post("/api/clients", json={"full_name": "Delete Me", "phone": "+7-000-000-00-00"}, headers=auth_headers)
    cid = r.json()["id"]
    r = client.delete(f"/api/clients/{cid}", headers=auth_headers)
    assert r.status_code == 200
    r = client.get(f"/api/clients/{cid}", headers=auth_headers)
    assert r.status_code == 404
