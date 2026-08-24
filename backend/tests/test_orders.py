from decimal import Decimal as D

from sqlalchemy import text

from app.core.security import create_access_token, hash_password
from app.models import User, UserRole

ORDER_PAYLOAD = {
    "pickup_address": "12 Anna Salai, Chennai",
    "pickup_pincode": "600001",
    "drop_address": "45 MG Road, Bengaluru",
    "drop_pincode": "560001",
    "length_cm": "50",
    "breadth_cm": "40",
    "height_cm": "30",
    "actual_weight_kg": "8",
    "order_type": "B2C",
    "payment_type": "COD",
}

QUOTE_EXPECTED = {
    "chargeable_weight": D("12"),
    "base_charge": D("720.00"),  # inter-zone B2C: 12kg x 60.00
    "cod_surcharge": D("30.00"),
    "total_charge": D("750.00"),
}


def create_order(client, headers, **overrides):
    return client.post("/orders", json={**ORDER_PAYLOAD, **overrides}, headers=headers)


def make_user(db_session, role, email=None):
    user = User(
        name="User",
        email=email or f"{role.value.lower()}.{id(db_session) & 0xffff}@example.com",
        password_hash=hash_password("password123"),
        role=role,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


def token_headers(user):
    return {"Authorization": f"Bearer {create_access_token(user_id=str(user.id), role=user.role.value)}"}


def test_quote_returns_engine_breakdown(pricing_world, client, customer_headers):
    response = client.post("/orders/quote", json=ORDER_PAYLOAD, headers=customer_headers)
    assert response.status_code == 200
    body = response.json()
    for key, expected in QUOTE_EXPECTED.items():
        assert D(body[key]) == expected
    assert body["pickup_zone"]["code"] == "CHE-CEN"
    assert body["drop_zone"]["code"] == "BLR-EST"
    assert body["zone_type"] == "INTER_ZONE"
    assert body["volumetric_weight"] == "12.00"


def test_quote_rejects_unmapped_pincode(client, customer_headers):
    response = client.post("/orders/quote", json={**ORDER_PAYLOAD, "drop_pincode": "999999"}, headers=customer_headers)
    assert response.status_code == 422


def test_agent_cannot_quote_or_create(client, make_auth_headers):
    agent_headers = make_auth_headers(UserRole.AGENT)
    assert client.post("/orders/quote", json=ORDER_PAYLOAD, headers=agent_headers).status_code == 403
    assert client.post("/orders", json=ORDER_PAYLOAD, headers=agent_headers).status_code == 403


def test_create_order_persists_quote_and_initial_tracking(pricing_world, client, customer_headers):
    created = create_order(client, customer_headers)
    assert created.status_code == 201
    order = created.json()

    for key, expected in QUOTE_EXPECTED.items():
        order_key = "chargeable_weight_kg" if key == "chargeable_weight" else key
        assert D(order[order_key]) == expected
    assert order["status"] == "PENDING"
    assert order["delivery_attempt"] == 1
    assert order["assigned_agent_id"] is None
    assert order["scheduled_delivery_date"] is not None

    tracking = client.get(f"/orders/{order['id']}/tracking", headers=customer_headers).json()
    assert len(tracking) == 1
    assert tracking[0]["status"] == "PENDING"
    assert tracking[0]["remarks"] == "Order created"


def test_customer_cannot_create_for_someone_else(client, customer_headers):
    other = client.post(
        "/orders", json={**ORDER_PAYLOAD, "customer_id": "00000000-0000-0000-0000-000000000000"}, headers=customer_headers
    )
    assert other.status_code == 403


def test_admin_creates_on_behalf_of_customer(pricing_world, client, admin_headers, db_session):
    customer = make_user(db_session, UserRole.CUSTOMER, email="behalf@example.com")

    created = create_order(client, admin_headers, customer_id=str(customer.id))
    assert created.status_code == 201
    assert created.json()["customer_id"] == str(customer.id)

    ghost = create_order(client, admin_headers, customer_id="00000000-0000-0000-0000-000000000099")
    assert ghost.status_code == 404


def test_past_scheduled_date_rejected(client, customer_headers):
    response = create_order(client, customer_headers, scheduled_delivery_date="2020-01-01")
    assert response.status_code == 422


def test_list_orders_scoped_by_role(pricing_world, client, customer_headers, admin_headers):
    first = create_order(client, customer_headers).json()
    second = create_order(client, customer_headers).json()
    on_behalf = create_order(client, admin_headers).json()

    own_ids = {o["id"] for o in client.get("/orders", headers=customer_headers).json()}
    assert {first["id"], second["id"]} <= own_ids
    assert on_behalf["id"] not in own_ids

    all_orders = client.get("/orders", headers=admin_headers).json()
    assert len(all_orders) >= 3

    pending_only = client.get("/orders", headers=admin_headers, params={"status": "PENDING"}).json()
    assert {o["status"] for o in pending_only} == {"PENDING"}


def test_order_detail_ownership_enforcement(pricing_world, client, customer_headers, admin_headers, db_session):
    order = create_order(client, customer_headers).json()
    stranger_headers = token_headers(make_user(db_session, UserRole.CUSTOMER))

    assert client.get(f"/orders/{order['id']}", headers=stranger_headers).status_code == 404
    assert client.get(f"/orders/{order['id']}/tracking", headers=stranger_headers).status_code == 404
    assert client.get(f"/orders/{order['id']}", headers=customer_headers).status_code == 200
    assert client.get(f"/orders/{order['id']}", headers=admin_headers).status_code == 200


def test_assigned_agent_can_view_order(pricing_world, client, customer_headers, db_session):
    from app.models import Order

    order = create_order(client, customer_headers).json()
    agent = make_user(db_session, UserRole.AGENT)

    db_session.execute(
        text("UPDATE orders SET assigned_agent_id = :aid WHERE id = :oid"),
        {"aid": str(agent.id), "oid": order["id"]},
    )
    db_session.commit()

    assert client.get(f"/orders/{order['id']}", headers=token_headers(agent)).status_code == 200
