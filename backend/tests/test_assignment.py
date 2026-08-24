"""Phase 6: agent assignment — availability/location, manual + auto assignment, BUSY lifecycle."""

import pytest
from fastapi import status
from sqlalchemy import text

from app.core.security import create_access_token
from app.models import UserRole
from tests.test_lifecycle import agent_update
from tests.test_orders import create_order as api_create_order
from tests.test_orders import make_user


def make_agent(db_session, *, name=None, lat=None, lng=None, zone_code=None, status="AVAILABLE"):
    from decimal import Decimal

    from app.models import AgentProfile

    user = make_user(db_session, UserRole.AGENT)
    profile = AgentProfile(
        user_id=user.id,
        availability_status=status,
        latitude=Decimal(lat) if lat is not None else None,
        longitude=Decimal(lng) if lng is not None else None,
    )
    if zone_code:
        zone_id = db_session.execute(text("SELECT id FROM zones WHERE code = :c"), {"c": zone_code}).scalar_one()
        profile.current_zone_id = zone_id
    db_session.add(profile)
    db_session.commit()
    return {
        "user": user,
        "profile": profile,
        "headers": {"Authorization": f"Bearer {create_access_token(user_id=str(user.id), role='AGENT')}"},
        "id": str(user.id),
    }


def pending_order(client, customer_headers):
    return api_create_order(client, customer_headers).json()


def auto_assign(client, admin_headers, order_id):
    return client.post(f"/admin/orders/{order_id}/auto-assign", headers=admin_headers)


def get_agent(client, admin_headers, agent_user_id):
    agents = client.get("/admin/agents", headers=admin_headers).json()
    return next(a for a in agents if a["user_id"] == agent_user_id)


# ---------------------------------------------------------------- availability / location


def test_availability_and_location_updates(client, db_session, pricing_world, admin_headers):
    agent = make_agent(db_session)
    response = client.patch(
        "/agent/availability", json={"availability_status": "OFFLINE"}, headers=agent["headers"]
    )
    assert response.status_code == 200, response.json()

    loc = client.patch(
        "/agent/location",
        json={"latitude": 13.0827, "longitude": 80.2707, "pincode": "600001"},
        headers=agent["headers"],
    )
    assert loc.status_code == 200, loc.json()
    body = loc.json()
    assert float(body["latitude"]) == pytest.approx(13.0827)
    assert body["current_zone_id"] == str(pricing_world["che_cen"].id)

    view = get_agent(client, admin_headers, agent["id"])
    assert view["availability_status"] == "OFFLINE"
    assert view["active_orders"] == 0


def test_cannot_go_offline_with_active_orders(client, db_session, customer_headers, admin_headers, pricing_world):
    agent = make_agent(db_session)
    order = pending_order(client, customer_headers)

    assigned = client.post(f"/admin/orders/{order['id']}/assign", json={"agent_id": agent["id"]}, headers=admin_headers)
    assert assigned.status_code == 200
    assert get_agent(client, admin_headers, agent["id"])["availability_status"] == "BUSY"

    offline = client.patch(
        "/agent/availability", json={"availability_status": "OFFLINE"}, headers=agent["headers"]
    )
    assert offline.status_code == status.HTTP_409_CONFLICT

    back_online = client.patch(
        "/agent/availability", json={"availability_status": "AVAILABLE"}, headers=agent["headers"]
    )
    assert back_online.status_code == 200


def test_location_unknown_pincode_422(client, db_session):
    agent = make_agent(db_session)
    response = client.patch(
        "/agent/location", json={"latitude": 13.0, "longitude": 80.0, "pincode": "999999"}, headers=agent["headers"]
    )
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT


# ---------------------------------------------------------------- auto assignment


def test_auto_assign_picks_nearest_available(client, db_session, pricing_world, customer_headers, admin_headers):
    near = make_agent(db_session, name="near", lat="13.083000", lng="80.271000", zone_code="CHE-CEN")
    far_same_zone = make_agent(db_session, name="far-same", lat="13.120000", lng="80.300000", zone_code="CHE-CEN")
    other_city = make_agent(db_session, name="blr", lat="12.978400", lng="77.640800", zone_code="BLR-EST")
    order = pending_order(client, customer_headers)

    result = auto_assign(client, admin_headers, order["id"])
    assert result.status_code == 200, result.json()
    body = result.json()
    assert body["assigned"] is True
    assert body["order_status"] == "ASSIGNED"
    assert body["assigned_agent_id"] == near["id"]

    # Determinism: same input -> same winner on repeat runs (fresh DB each test anyway,
    # so assert the ordering logic held: zone-mates beat cross-city).
    assert far_same_zone["id"] != body["assigned_agent_id"]
    assert other_city["id"] != body["assigned_agent_id"]


def test_auto_assign_skips_busy_and_offline_agents(client, db_session, pricing_world, customer_headers, admin_headers):
    closer_but_busy = make_agent(
        db_session, name="busy", lat="13.083000", lng="80.271000", zone_code="CHE-CEN", status="BUSY"
    )
    closer_but_offline = make_agent(
        db_session, name="off", lat="13.084000", lng="80.272000", zone_code="CHE-CEN", status="OFFLINE"
    )
    available = make_agent(db_session, name="avail", lat="13.100000", lng="80.290000", zone_code="CHE-CEN")
    order = pending_order(client, customer_headers)

    result = auto_assign(client, admin_headers, order["id"])
    assert result.json()["assigned_agent_id"] == available["id"]
    assert {closer_but_busy["id"], closer_but_offline["id"]} & {result.json()["assigned_agent_id"]} == set()


def test_auto_assign_no_agents_available(client, db_session, pricing_world, customer_headers, admin_headers):
    order = pending_order(client, customer_headers)
    result = auto_assign(client, admin_headers, order["id"])
    assert result.status_code == 200
    body = result.json()
    assert body["assigned"] is False
    assert "No available agents" in body["message"]
    assert body["order_status"] == "PENDING"


def test_assignment_makes_agent_busy_and_blocks_reassignment(client, db_session, pricing_world, customer_headers, admin_headers):
    agent = make_agent(db_session, name="solo", lat="13.083000", lng="80.271000", zone_code="CHE-CEN")
    o1 = pending_order(client, customer_headers)
    o2 = pending_order(client, customer_headers)

    first = auto_assign(client, admin_headers, o1["id"])
    assert first.json()["assigned_agent_id"] == agent["id"]

    second = auto_assign(client, admin_headers, o2["id"])
    assert second.json()["assigned"] is False

    manual = client.post(f"/admin/orders/{o2['id']}/assign", json={"agent_id": agent["id"]}, headers=admin_headers)
    assert manual.status_code == status.HTTP_409_CONFLICT


def test_terminal_status_releases_agent(client, db_session, pricing_world, customer_headers, admin_headers):
    agent = make_agent(db_session, name="releaseme", lat="13.083000", lng="80.271000", zone_code="CHE-CEN")
    o1 = pending_order(client, customer_headers)
    assert auto_assign(client, admin_headers, o1["id"]).json()["assigned"] is True
    o2 = pending_order(client, customer_headers)
    assert auto_assign(client, admin_headers, o2["id"]).json()["assigned"] is False

    for step in ["PICKED_UP", "IN_TRANSIT", "OUT_FOR_DELIVERY", "DELIVERED"]:
        assert agent_update(client, agent["headers"], o1["id"], step).status_code == 200

    third = auto_assign(client, admin_headers, o2["id"])
    assert third.json()["assigned_agent_id"] == agent["id"]


# ---------------------------------------------------------------- manual assignment


def test_manual_assign_happy_path_and_tracking_row(client, db_session, pricing_world, customer_headers, admin_headers, test_engine):
    agent = make_agent(db_session, name="manualguy")
    order = pending_order(client, customer_headers)

    response = client.post(
        f"/admin/orders/{order['id']}/assign", json={"agent_id": agent["id"]}, headers=admin_headers
    )
    assert response.status_code == 200, response.json()
    body = response.json()
    assert body["status"] == "ASSIGNED"
    assert body["assigned_agent_id"] == agent["id"]

    timeline = client.get(f"/orders/{order['id']}/tracking", headers=admin_headers).json()
    assert [e["status"] for e in timeline] == ["PENDING", "ASSIGNED"]


def test_manual_assign_validations(client, db_session, pricing_world, customer_headers, admin_headers):
    agent = make_agent(db_session, name="v1", status="OFFLINE")
    busy = make_agent(db_session, name="v2", status="BUSY")
    customer = make_user(db_session, UserRole.CUSTOMER)
    order = pending_order(client, customer_headers)

    missing = client.post(f"/admin/orders/{order['id']}/assign", json={"agent_id": str(customer.id)}, headers=admin_headers)
    assert missing.status_code == status.HTTP_404_NOT_FOUND

    unknown = client.post(f"/admin/orders/{order['id']}/assign", json={"agent_id": "00000000-0000-0000-0000-000000000000"}, headers=admin_headers)
    assert unknown.status_code == status.HTTP_404_NOT_FOUND

    offline = client.post(f"/admin/orders/{order['id']}/assign", json={"agent_id": agent["id"]}, headers=admin_headers)
    assert offline.status_code == status.HTTP_409_CONFLICT

    busy_resp = client.post(f"/admin/orders/{order['id']}/assign", json={"agent_id": busy["id"]}, headers=admin_headers)
    assert busy_resp.status_code == status.HTTP_409_CONFLICT


def test_manual_assign_twice_conflicts_on_non_pending(client, db_session, pricing_world, customer_headers, admin_headers):
    agent = make_agent(db_session, name="twice")
    order = pending_order(client, customer_headers)
    first = client.post(f"/admin/orders/{order['id']}/assign", json={"agent_id": agent["id"]}, headers=admin_headers)
    assert first.status_code == 200
    second = client.post(f"/admin/orders/{order['id']}/assign", json={"agent_id": agent["id"]}, headers=admin_headers)
    assert second.status_code == status.HTTP_409_CONFLICT


# ---------------------------------------------------------------- rbac


def test_rbac_customer_cannot_hit_agent_or_admin_assignment_routes(client, db_session, customer_headers):
    assert client.patch("/agent/availability", json={"availability_status": "OFFLINE"}, headers=customer_headers).status_code == status.HTTP_403_FORBIDDEN
    assert client.patch("/agent/location", json={"latitude": 13.0, "longitude": 80.0}, headers=customer_headers).status_code == status.HTTP_403_FORBIDDEN
    assert client.get("/admin/agents", headers=customer_headers).status_code == status.HTTP_403_FORBIDDEN
