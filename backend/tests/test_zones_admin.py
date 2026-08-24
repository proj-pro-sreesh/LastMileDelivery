import uuid

from app.models import User, UserRole


def create_zone(client, headers, name="Test Zone", code=None):
    return client.post(
        "/admin/zones",
        json={"name": name, "code": code or f"TZ-{uuid.uuid4().hex[:6].upper()}"},
        headers=headers,
    )


def test_admin_endpoints_require_authentication(client):
    assert client.get("/admin/zones").status_code == 401
    assert client.post("/admin/zones", json={"name": "X", "code": "X-1"}).status_code == 401


def test_customer_cannot_access_admin_endpoints(client, make_auth_headers):
    customer_headers = make_auth_headers(UserRole.CUSTOMER)
    assert client.get("/admin/zones", headers=customer_headers).status_code == 403
    response = create_zone(client, customer_headers)
    assert response.status_code == 403


def test_agent_cannot_create_rate_card(client, make_auth_headers):
    agent_headers = make_auth_headers(UserRole.AGENT)
    response = client.post(
        "/admin/rates",
        json={
            "order_type": "B2C",
            "from_zone_id": str(uuid.uuid4()),
            "to_zone_id": str(uuid.uuid4()),
            "rate_per_kg": "40.00",
            "minimum_charge": "100.00",
        },
        headers=agent_headers,
    )
    assert response.status_code == 403


def test_zone_crud_lifecycle(client, make_auth_headers):
    admin_headers = make_auth_headers(UserRole.ADMIN)

    created = create_zone(client, admin_headers)
    assert created.status_code == 201
    zone = created.json()

    duplicate = create_zone(client, admin_headers, name="Other", code=zone["code"])
    assert duplicate.status_code == 409

    updated = client.put(f"/admin/zones/{zone['id']}", json={"name": "Renamed"}, headers=admin_headers)
    assert updated.status_code == 200 and updated.json()["name"] == "Renamed"

    listed = client.get("/admin/zones", headers=admin_headers)
    assert any(z["id"] == zone["id"] for z in listed.json())

    deleted = client.delete(f"/admin/zones/{zone['id']}", headers=admin_headers)
    assert deleted.status_code == 204
    missing = client.delete(f"/admin/zones/{zone['id']}", headers=admin_headers)
    assert missing.status_code == 404


def test_zone_with_area_cannot_be_deleted(client, make_auth_headers):
    admin_headers = make_auth_headers(UserRole.ADMIN)
    zone = create_zone(client, admin_headers).json()
    area = client.post(
        "/admin/areas",
        json={"name": "T Nagar", "pincode": "600017", "zone_id": zone["id"]},
        headers=admin_headers,
    )
    assert area.status_code == 201

    conflict = client.delete(f"/admin/zones/{zone['id']}", headers=admin_headers)
    assert conflict.status_code == 409


def test_area_pincode_validation_and_uniqueness(client, make_auth_headers):
    admin_headers = make_auth_headers(UserRole.ADMIN)
    zone = create_zone(client, admin_headers).json()

    ok = client.post(
        "/admin/areas", json={"name": "Anna Nagar", "pincode": "600040", "zone_id": zone["id"]}, headers=admin_headers
    )
    assert ok.status_code == 201

    dup = client.post(
        "/admin/areas", json={"name": "Dup", "pincode": "600040", "zone_id": zone["id"]}, headers=admin_headers
    )
    assert dup.status_code == 409

    bad_format = client.post(
        "/admin/areas", json={"name": "Bad", "pincode": "60040", "zone_id": zone["id"]}, headers=admin_headers
    )
    assert bad_format.status_code == 422

    unknown_zone = client.post(
        "/admin/areas",
        json={"name": "Ghost", "pincode": "600041", "zone_id": str(uuid.uuid4())},
        headers=admin_headers,
    )
    assert unknown_zone.status_code == 404


def test_rate_card_crud_and_duplicates(client, make_auth_headers):
    admin_headers = make_auth_headers(UserRole.ADMIN)
    z1 = create_zone(client, admin_headers).json()
    z2 = create_zone(client, admin_headers).json()

    card_payload = {
        "order_type": "B2B",
        "from_zone_id": z1["id"],
        "to_zone_id": z2["id"],
        "rate_per_kg": "45.50",
        "minimum_charge": "120.00",
    }
    created = client.post("/admin/rates", json=card_payload, headers=admin_headers)
    assert created.status_code == 201

    dup = client.post("/admin/rates", json=card_payload, headers=admin_headers)
    assert dup.status_code == 409

    updated = client.put(
        f"/admin/rates/{created.json()['id']}", json={"rate_per_kg": "50.00"}, headers=admin_headers
    )
    assert updated.status_code == 200 and updated.json()["rate_per_kg"] == "50.00"

    assert client.delete(f"/admin/rates/{created.json()['id']}", headers=admin_headers).status_code == 204


def test_cod_rate_crud_and_duplicate(client, make_auth_headers):
    admin_headers = make_auth_headers(UserRole.ADMIN)

    created = client.post("/admin/cod-rates", json={"order_type": "B2C", "surcharge": "30.00"}, headers=admin_headers)
    assert created.status_code == 201

    dup = client.post("/admin/cod-rates", json={"order_type": "B2C", "surcharge": "35.00"}, headers=admin_headers)
    assert dup.status_code == 409

    other = client.post("/admin/cod-rates", json={"order_type": "B2B", "surcharge": "25.00"}, headers=admin_headers)
    assert other.status_code == 201

    listed = client.get("/admin/cod-rates", headers=admin_headers)
    assert len(listed.json()) == 2
