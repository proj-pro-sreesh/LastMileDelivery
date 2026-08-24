"""Phase 7: failed delivery & reschedule — attempt counting, FAILED->PENDING flow, reassignment."""

from datetime import date, timedelta

import pytest
from fastapi import status

from tests.test_assignment import auto_assign, make_agent
from tests.test_lifecycle import agent_update
from tests.test_orders import create_order as api_create_order


@pytest.fixture
def failed_out_for_delivery_order(client, db_session, pricing_world, customer_headers, admin_headers):
    """Order driven to OUT_FOR_DELIVERY by an assigned agent (not yet FAILED)."""
    agent = make_agent(db_session, lat="13.083000", lng="80.271000", zone_code="CHE-CEN")
    order = api_create_order(client, customer_headers).json()
    assert client.post(
        f"/admin/orders/{order['id']}/assign", json={"agent_id": agent["id"]}, headers=admin_headers
    ).status_code == 200
    for step in ["PICKED_UP", "IN_TRANSIT", "OUT_FOR_DELIVERY"]:
        assert agent_update(client, agent["headers"], order["id"], step).status_code == 200
    return {"order": order, "agent": agent}


def fail_it(client, failed):
    return agent_update(client, failed["agent"]["headers"], failed["order"]["id"], "FAILED", remarks="Customer not home")


def test_failed_increments_attempt_and_releases_agent(
    client, db_session, customer_headers, admin_headers, failed_out_for_delivery_order
):
    failed = failed_out_for_delivery_order
    response = fail_it(client, failed)
    assert response.status_code == 200, response.json()

    body = response.json()
    assert body["status"] == "FAILED"
    assert body["delivery_attempt"] == 2

    agents = client.get("/admin/agents", headers=admin_headers).json()
    assert next(a for a in agents if a["user_id"] == failed["agent"]["id"])["availability_status"] == "AVAILABLE"


def test_reschedule_returns_failed_order_to_queue(
    client, db_session, pricing_world, customer_headers, admin_headers, failed_out_for_delivery_order
):
    failed = failed_out_for_delivery_order
    assert fail_it(client, failed).status_code == 200

    response = client.post(
        f"/admin/orders/{failed['order']['id']}/reschedule",
        json={"remarks": "Customer asked for evening redelivery"},
        headers=admin_headers,
    )
    assert response.status_code == 200, response.json()
    body = response.json()
    assert body["status"] == "PENDING"
    assert body["assigned_agent_id"] is None
    assert body["delivery_attempt"] == 2  # consumed attempt is preserved
    assert body["scheduled_delivery_date"] == str(date.today() + timedelta(days=1))

    timeline = [e["status"] for e in client.get(f"/orders/{failed['order']['id']}/tracking", headers=admin_headers).json()]
    assert timeline[-1] == "PENDING"


def test_rescheduled_order_is_reassignable_and_deliverable(
    client, db_session, pricing_world, customer_headers, admin_headers, failed_out_for_delivery_order
):
    failed = failed_out_for_delivery_order
    assert fail_it(client, failed).status_code == 200
    resched = client.post(
        f"/admin/orders/{failed['order']['id']}/reschedule", json={}, headers=admin_headers
    )
    assert resched.status_code == 200

    result = auto_assign(client, admin_headers, failed["order"]["id"])
    assert result.status_code == 200, result.json()
    assert result.json()["assigned"] is True
    assert result.json()["assigned_agent_id"] == failed["agent"]["id"]  # nearest again after release

    for step in ["PICKED_UP", "IN_TRANSIT", "OUT_FOR_DELIVERY", "DELIVERED"]:
        response = agent_update(client, failed["agent"]["headers"], failed["order"]["id"], step)
        assert response.status_code == 200, response.json()

    final = response.json()
    assert final["delivery_attempt"] == 2  # successful retry does not inflate attempts


def test_second_failure_accumulates_attempts(
    client, db_session, pricing_world, customer_headers, admin_headers, failed_out_for_delivery_order
):
    failed = failed_out_for_delivery_order
    assert fail_it(client, failed).json()["delivery_attempt"] == 2
    assert (
        client.post(f"/admin/orders/{failed['order']['id']}/reschedule", json={}, headers=admin_headers).status_code
        == 200
    )
    assert auto_assign(client, admin_headers, failed["order"]["id"]).json()["assigned"] is True
    for step in ["PICKED_UP", "IN_TRANSIT", "OUT_FOR_DELIVERY"]:
        assert agent_update(client, failed["agent"]["headers"], failed["order"]["id"], step).status_code == 200
    second_fail = agent_update(
        client, failed["agent"]["headers"], failed["order"]["id"], "FAILED", remarks="Address unreachable"
    )
    assert second_fail.status_code == 200
    assert second_fail.json()["delivery_attempt"] == 3


def test_reschedule_rejects_non_failed_orders(client, db_session, pricing_world, customer_headers, admin_headers):
    order = api_create_order(client, customer_headers).json()  # still PENDING
    response = client.post(f"/admin/orders/{order['id']}/reschedule", json={}, headers=admin_headers)
    assert response.status_code == status.HTTP_409_CONFLICT


def test_admin_override_cannot_do_failed_to_pending(
    client, db_session, pricing_world, customer_headers, admin_headers, failed_out_for_delivery_order
):
    failed = failed_out_for_delivery_order
    assert fail_it(client, failed).status_code == 200

    override = client.patch(
        f"/admin/orders/{failed['order']['id']}/status",
        json={"status": "PENDING", "remarks": "trying the back door"},
        headers=admin_headers,
    )
    assert override.status_code == status.HTTP_409_CONFLICT
    assert "reschedule" in override.json()["detail"].lower()


def test_reschedule_custom_future_date_and_past_date_422(
    client, db_session, pricing_world, customer_headers, admin_headers, failed_out_for_delivery_order
):
    failed = failed_out_for_delivery_order
    assert fail_it(client, failed).status_code == 200

    future = date.today() + timedelta(days=3)
    ok = client.post(
        f"/admin/orders/{failed['order']['id']}/reschedule",
        json={"scheduled_delivery_date": future.isoformat()},
        headers=admin_headers,
    )
    assert ok.status_code == 200
    assert ok.json()["scheduled_delivery_date"] == future.isoformat()


def test_reschedule_rejects_past_date(client, db_session, pricing_world, customer_headers, admin_headers, failed_out_for_delivery_order):
    failed = failed_out_for_delivery_order
    assert fail_it(client, failed).status_code == 200

    past = (date.today() - timedelta(days=1)).isoformat()
    response = client.post(
        f"/admin/orders/{failed['order']['id']}/reschedule",
        json={"scheduled_delivery_date": past},
        headers=admin_headers,
    )
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT


def test_reschedule_rbac(client, db_session, pricing_world, make_auth_headers, customer_headers, admin_headers, failed_out_for_delivery_order):
    failed = failed_out_for_delivery_order
    assert fail_it(client, failed).status_code == 200

    agent_headers = failed["agent"]["headers"]
    assert (
        client.post(f"/admin/orders/{failed['order']['id']}/reschedule", json={}, headers=agent_headers).status_code
        == status.HTTP_403_FORBIDDEN
    )
    assert (
        client.post(f"/admin/orders/{failed['order']['id']}/reschedule", json={}, headers=customer_headers).status_code
        == status.HTTP_403_FORBIDDEN
    )
    assert (
        client.post(f"/admin/orders/{failed['order']['id']}/reschedule", json={}).status_code
        == status.HTTP_401_UNAUTHORIZED
    )
