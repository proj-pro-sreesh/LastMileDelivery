import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

from app.core.security import create_access_token
from app.models import UserRole
from app.models.enums import OrderStatus

from tests.test_orders import create_order as api_create_order, make_user


@pytest.fixture
def assigned_order(client, customer_headers, pricing_world, db_session):
    """A PENDING order created by a customer, then assigned to an agent (PENDING -> ASSIGNED).

    Simulates what the Phase 6 assignment service will do: set the agent AND move
    status to ASSIGNED with a tracking row.
    """
    order = api_create_order(client, customer_headers).json()
    agent = make_user(db_session, UserRole.AGENT)
    db_session.execute(
        text(
            "UPDATE orders SET assigned_agent_id = :aid, status = 'ASSIGNED' WHERE id = :oid"
        ),
        {"aid": str(agent.id), "oid": order["id"]},
    )
    db_session.execute(
        text("INSERT INTO order_tracking (id, order_id, status, actor_id, remarks) "
             "VALUES (gen_random_uuid(), :oid, 'ASSIGNED', :aid, 'Assigned to agent')"),
        {"oid": order["id"], "aid": str(agent.id)},
    )
    db_session.commit()
    return {
        "order": order,
        "agent": agent,
        "agent_headers": {"Authorization": f"Bearer {create_access_token(user_id=str(agent.id), role='AGENT')}"},
    }


def agent_update(client, headers, order_id, new_status, remarks=None):
    return client.patch(
        f"/agent/orders/{order_id}/status",
        json={"status": new_status, **({"remarks": remarks} if remarks else {})},
        headers=headers,
    )


def tracking_statuses(client, customer_headers, order_id):
    entries = client.get(f"/orders/{order_id}/tracking", headers=customer_headers).json()
    return [e["status"] for e in entries]


def test_full_delivery_lifecycle_happy_path(client, customer_headers, assigned_order):
    order_id = assigned_order["order"]["id"]
    flow = ["PICKED_UP", "IN_TRANSIT", "OUT_FOR_DELIVERY", "DELIVERED"]

    for target in flow:
        response = agent_update(client, assigned_order["agent_headers"], order_id, target)
        assert response.status_code == 200, response.json()
        assert response.json()["status"] == target

    assert tracking_statuses(client, customer_headers, order_id) == [
        "PENDING",
        "ASSIGNED",
        *flow,
    ]


def test_invalid_transition_rejected_with_409(client, customer_headers, assigned_order):
    order_id = assigned_order["order"]["id"]

    # Cannot skip statuses from ASSIGNED
    skipped = agent_update(client, assigned_order["agent_headers"], order_id, "IN_TRANSIT")
    assert skipped.status_code == 409

    # Advance one step, then try another illegal jump
    assert agent_update(client, assigned_order["agent_headers"], order_id, "PICKED_UP").status_code == 200
    backwards = agent_update(client, assigned_order["agent_headers"], order_id, "ASSIGNED")
    assert backwards.status_code == 409
    jump = agent_update(client, assigned_order["agent_headers"], order_id, "DELIVERED")
    assert jump.status_code == 409


def test_terminal_states_accept_no_further_updates(client, customer_headers, assigned_order):
    order_id = assigned_order["order"]["id"]
    for target in ["PICKED_UP", "IN_TRANSIT", "OUT_FOR_DELIVERY", "DELIVERED"]:
        agent_update(client, assigned_order["agent_headers"], order_id, target)

    after_end = agent_update(client, assigned_order["agent_headers"], order_id, "PICKED_UP")
    assert after_end.status_code == 409


def test_agent_cannot_touch_unassigned_orders(client, customer_headers, pricing_world, make_auth_headers):
    order = api_create_order(client, customer_headers).json()
    stranger = make_auth_headers(UserRole.AGENT)
    response = agent_update(client, stranger, order["id"], "PICKED_UP")
    assert response.status_code == 404


def test_non_agents_blocked_from_agent_routes(client, customer_headers):
    assert client.get("/agent/orders", headers=customer_headers).status_code == 403
    assert client.get("/agent/orders").status_code == 401


def test_agent_orders_listing_only_shows_assigned(
    client, customer_headers, pricing_world, db_session, make_auth_headers
):
    o1 = api_create_order(client, customer_headers).json()
    o2 = api_create_order(client, customer_headers).json()
    agent = make_user(db_session, UserRole.AGENT)

    db_session.execute(
        text("UPDATE orders SET assigned_agent_id = :aid WHERE id = :oid"), {"aid": str(agent.id), "oid": o1["id"]}
    )
    db_session.commit()

    listing = client.get(
        "/agent/orders",
        headers={"Authorization": f"Bearer {create_access_token(user_id=str(agent.id), role='AGENT')}"},
    ).json()
    assert [o["id"] for o in listing] == [o1["id"]]
    assert o2["id"] not in {o["id"] for o in listing}


def test_failed_delivery_requires_reason_and_records_it(client, customer_headers, assigned_order):
    order_id = assigned_order["order"]["id"]
    agent_headers = assigned_order["agent_headers"]

    assert agent_update(client, agent_headers, order_id, "PICKED_UP").status_code == 200
    assert agent_update(client, agent_headers, order_id, "IN_TRANSIT").status_code == 200
    assert agent_update(client, agent_headers, order_id, "OUT_FOR_DELIVERY").status_code == 200

    missing_reason = agent_update(client, agent_headers, order_id, "FAILED")
    assert missing_reason.status_code == 422

    failed = agent_update(client, agent_headers, order_id, "FAILED", remarks="Customer not home")
    assert failed.status_code == 200
    assert failed.json()["status"] == "FAILED"

    entries = client.get(f"/orders/{order_id}/tracking", headers=customer_headers).json()
    assert entries[-1]["status"] == "FAILED"
    assert entries[-1]["remarks"] == "Customer not home"


def test_admin_can_override_status_anywhere(client, admin_headers, customer_headers, assigned_order):
    order_id = assigned_order["order"]["id"]

    override = client.patch(
        f"/admin/orders/{order_id}/status",
        json={"status": "CANCELLED", "remarks": "Customer requested cancellation"},
        headers=admin_headers,
    )
    assert override.status_code == 200
    assert override.json()["status"] == "CANCELLED"
    assert tracking_statuses(client, customer_headers, order_id)[-2:] == ["ASSIGNED", "CANCELLED"]


def test_admin_override_requires_remarks_and_rejects_noop(client, admin_headers, customer_headers, assigned_order):
    order_id = assigned_order["order"]["id"]

    no_remarks = client.patch(
        f"/admin/orders/{order_id}/status", json={"status": "CANCELLED"}, headers=admin_headers
    )
    assert no_remarks.status_code == 422

    current_status = client.get(f"/orders/{order_id}", headers=admin_headers).json()["status"]
    noop = client.patch(
        f"/admin/orders/{order_id}/status",
        json={"status": current_status, "remarks": "same state"},
        headers=admin_headers,
    )
    assert noop.status_code == 409


def test_admin_can_override_out_of_terminal_state(client, admin_headers, customer_headers, assigned_order):
    order_id = assigned_order["order"]["id"]
    for target in ["PICKED_UP", "IN_TRANSIT", "OUT_FOR_DELIVERY", "DELIVERED"]:
        agent_update(client, assigned_order["agent_headers"], order_id, target)

    revived = client.patch(
        f"/admin/orders/{order_id}/status",
        json={"status": "OUT_FOR_DELIVERY", "remarks": "Reopened after investigation"},
        headers=admin_headers,
    )
    assert revived.status_code == 200
    assert revived.json()["status"] == "OUT_FOR_DELIVERY"


def test_customer_cannot_use_admin_override(client, customer_headers, assigned_order):
    order_id = assigned_order["order"]["id"]
    response = client.patch(
        f"/admin/orders/{order_id}/status",
        json={"status": "DELIVERED", "remarks": "not allowed"},
        headers=customer_headers,
    )
    assert response.status_code == 403


def test_tracking_rows_are_immutable_at_db_level(client, customer_headers, assigned_order, test_engine):
    order_id = assigned_order["order"]["id"]
    agent_update(client, assigned_order["agent_headers"], order_id, "PICKED_UP")

    before = tracking_statuses(client, customer_headers, order_id)

    with pytest.raises(DBAPIError) as exc_info:
        with test_engine.begin() as conn:
            conn.execute(text("UPDATE order_tracking SET status = 'CANCELLED'"))
    assert "immutable" in str(exc_info.value)

    with pytest.raises(DBAPIError):
        with test_engine.begin() as conn:
            conn.execute(text("DELETE FROM order_tracking"))

    assert tracking_statuses(client, customer_headers, order_id) == before
