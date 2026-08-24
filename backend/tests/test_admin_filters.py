"""GAP 2: admin order filters — status, zone (pickup OR drop), agent, combined."""

import uuid

from app.models import UserRole
from tests.test_assignment import auto_assign as api_auto_assign, make_agent
from tests.test_lifecycle import agent_update
from tests.test_orders import create_order as api_create_order


def _drive_to_delivered(client, admin_headers, agent, order_id):
    assert client.post(
        f"/admin/orders/{order_id}/assign", json={"agent_id": agent["id"]}, headers=admin_headers
    ).status_code == 200
    for step in ["PICKED_UP", "IN_TRANSIT", "OUT_FOR_DELIVERY", "DELIVERED"]:
        assert agent_update(client, agent["headers"], order_id, step).status_code == 200


def test_admin_filters_by_zone_pickup_or_drop(client, db_session, pricing_world, customer_headers, admin_headers):
    # Intra-zone order: both legs CHE-CEN. Cross-city order: pickup CHE-CEN, drop BLR-EST.
    intra = api_create_order(client, customer_headers, drop_pincode="600002").json()
    cross = api_create_order(client, customer_headers).json()

    che_cen = pricing_world["che_cen"]
    blr_est = pricing_world["blr_est"]

    by_zone = client.get(f"/orders?zone_id={che_cen.id}", headers=admin_headers).json()
    assert {o["id"] for o in by_zone} == {intra["id"], cross["id"]}

    only_blr_drop = client.get(f"/orders?zone_id={blr_est.id}", headers=admin_headers).json()
    assert {o["id"] for o in only_blr_drop} == {cross["id"]}


def test_admin_filters_by_agent(client, db_session, pricing_world, customer_headers, admin_headers):
    agent = make_agent(db_session, lat="13.083000", lng="80.271000", zone_code="CHE-CEN")
    mine = api_create_order(client, customer_headers).json()
    other = api_create_order(client, customer_headers).json()
    assert api_auto_assign(client, admin_headers, mine["id"]).json()["assigned"] is True

    filtered = client.get(f"/orders?agent_id={agent['id']}", headers=admin_headers).json()
    assert {o["id"] for o in filtered} == {mine["id"]}
    assert other["id"] not in {o["id"] for o in filtered}


def test_admin_combines_status_and_agent_filters(client, db_session, pricing_world, customer_headers, admin_headers):
    agent = make_agent(db_session, lat="13.083000", lng="80.271000", zone_code="CHE-CEN")
    assigned_order = api_create_order(client, customer_headers).json()
    delivered_order = api_create_order(client, customer_headers).json()
    _drive_to_delivered(client, admin_headers, agent, delivered_order["id"])  # releases the agent after DELIVERED
    assert api_auto_assign(client, admin_headers, assigned_order["id"]).json()["assigned"] is True

    # The delivered order was released from the agent; filter on status only.
    active = client.get(f"/orders?status=ASSIGNED&agent_id={agent['id']}", headers=admin_headers).json()
    assert [o["id"] for o in active] == [assigned_order["id"]]


def test_filter_combo_with_no_matches_returns_empty_list(
    client, db_session, pricing_world, customer_headers, admin_headers
):
    api_create_order(client, customer_headers)  # PENDING order exists
    response = client.get(f"/orders?agent_id={uuid.uuid4()}", headers=admin_headers)
    assert response.status_code == 200
    assert response.json() == []


def test_non_admin_cannot_use_zone_or_agent_filters(
    client, db_session, pricing_world, customer_headers, make_auth_headers
):
    api_create_order(client, customer_headers)
    agent_user = make_auth_headers(UserRole.AGENT)

    zone_resp = client.get(f"/orders?zone_id={uuid.uuid4()}", headers=customer_headers)
    agent_resp = client.get(f"/orders?agent_id={uuid.uuid4()}", headers=agent_user)

    assert zone_resp.status_code == 403
    assert agent_resp.status_code == 403
