def test_create_order(client, auth_headers):
    r = client.post("/api/clients", json={"full_name": "Клиент", "phone": "+7-999-999-99-99"}, headers=auth_headers)
    cid = r.json()["id"]
    r = client.post("/api/services", json={"name": "Тестовая услуга", "price": 500, "category": "repair"}, headers=auth_headers)
    sid = r.json()["id"]
    r = client.post("/api/orders", json={
        "client_id": cid,
        "order_type": "repair",
        "items": [{"service_id": sid, "quantity": 2, "price": 500}],
    }, headers=auth_headers)
    assert r.status_code == 200
    data = r.json()
    assert data["total_price"] == 1000
    assert data["status"] == "active"


def test_list_orders(client, auth_headers):
    r = client.get("/api/orders", headers=auth_headers)
    assert r.status_code == 200


def test_get_services(client, auth_headers):
    r = client.get("/api/services?category=repair", headers=auth_headers)
    assert r.status_code == 200
