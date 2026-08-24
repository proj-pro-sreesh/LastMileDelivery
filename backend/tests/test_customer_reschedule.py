"""GAP 1: customer-owned rescheduling of FAILED orders."""

from datetime import date, timedelta

import pytest
from fastapi import status
from sqlalchemy import select

from app.models import Reschedule, UserRole
from tests.test_assignment import get_agent, make_agent
from tests.test_lifecycle import agent_update
from tests.test_orders import create_order as api_create_order


@pytest.fixture
def failed_order(client, db_session, pricing_world, customer_headers, admin_headers):
    """Order driven to FAILED by an assigned agent; returns owner headers + agent."""
    agent = make_agent(db_session, lat="13.083000", lng="80.271000", zone_code="CHE-CEN")
    order = api_create_order(client, customer_headers).json()
    assert client.post(
        f"/admin/orders/{order['id']}/assign", json={"agent_id": agent["id"]}, headers=admin_headers
    ).status_code == 200
    for step in ["PICKED_UP", "IN_TRANSIT", "OUT_FOR_DELIVERY"]:
        assert agent_update(client, agent["headers"], order["id"], step).status_code == 200
    response = agent_update(client, agent["headers"], order["id"], "FAILED", remarks="Customer not home")
    assert response.status_code == 200
    return {"order": order, "agent": agent, "customer_headers": customer_headers}


def reschedule(client, customer_headers, order_id, payload):
    return client.post(f"/orders/{order_id}/reschedule", json=payload, headers=customer_headers)


def future(days=3):
    return (date.today() + timedelta(days=days)).isoformat()


def test_customer_reschedules_own_failed_order(
    client, db_session, pricing_world, admin_headers, failed_order
):
    failed = failed_order
    attempts_before = client.get(
        f"/orders/{failed['order']['id']}", headers=failed["customer_headers"]
    ).json()["delivery_attempt"]
    response = reschedule(
        client,
        failed["customer_headers"],
        failed["order"]["id"],
        {"scheduled_delivery_date": future(), "remarks": "Evening please"},
    )
    assert response.status_code == 200, response.json()
    body = response.json()
    assert body["status"] in ("PENDING", "ASSIGNED")  # ASSIGNED when an agent is auto-picked
    assert body["scheduled_delivery_date"] == future()
    # A customer-scheduled retry opens a fresh delivery attempt.
    assert body["delivery_attempt"] == attempts_before + 1

    row = db_session.scalar(select(Reschedule).where(Reschedule.order_id == failed["order"]["id"]))
    assert row is not None
    assert row.requested_by_role == "CUSTOMER"
    assert str(row.new_scheduled_date) == future()
    assert row.remarks == "Evening please"

    timeline = [
        e["status"]
        for e in client.get(
            f"/orders/{failed['order']['id']}/tracking", headers=failed["customer_headers"]
        ).json()
    ]
    assert timeline[-1] in ("PENDING", "ASSIGNED")


def test_customer_cannot_reschedule_another_customers_order(
    client, db_session, pricing_world, make_auth_headers, failed_order
):
    stranger = make_auth_headers(UserRole.CUSTOMER, name="Stranger")
    response = reschedule(client, stranger, failed_order["order"]["id"], {"scheduled_delivery_date": future()})
    assert response.status_code == status.HTTP_404_NOT_FOUND


def test_customer_cannot_reschedule_non_failed_order(
    client, db_session, pricing_world, customer_headers
):
    order = api_create_order(client, customer_headers).json()  # stays PENDING
    response = reschedule(client, customer_headers, order["id"], {"scheduled_delivery_date": future()})
    assert response.status_code == status.HTTP_409_CONFLICT


def test_customer_reschedule_rejects_past_date(client, db_session, pricing_world, failed_order):
    failed = failed_order
    past = (date.today() - timedelta(days=1)).isoformat()
    response = reschedule(
        client, failed["customer_headers"], failed["order"]["id"], {"scheduled_delivery_date": past}
    )
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT


def test_new_agent_assigned_and_previous_released_after_customer_reschedule(
    client, db_session, pricing_world, admin_headers, failed_order
):
    """Retry goes through the assignment engine: nearest AVAILABLE agent wins."""
    failed = failed_order
    closer = make_agent(db_session, lat="13.082800", lng="80.270900", zone_code="CHE-CEN")

    response = reschedule(
        client, failed["customer_headers"], failed["order"]["id"], {"scheduled_delivery_date": future()}
    )
    assert response.status_code == 200
    body = response.json()

    assert body["assigned_agent_id"] == closer["id"]
    assert body["status"] == "ASSIGNED"
    assert get_agent(client, admin_headers, closer["id"])["availability_status"] == "BUSY"
    if failed["agent"]["id"] != closer["id"]:
        assert get_agent(client, admin_headers, failed["agent"]["id"])["availability_status"] == "AVAILABLE"


def test_customer_reschedule_with_no_agents_available_stays_pending(
    client, db_session, pricing_world, admin_headers, failed_order
):
    """No AVAILABLE agents -> order parks in the PENDING queue instead of failing."""
    failed = failed_order
    offline = client.patch(
        "/agent/availability", json={"availability_status": "OFFLINE"}, headers=failed["agent"]["headers"]
    )
    assert offline.status_code == 200

    response = reschedule(
        client, failed["customer_headers"], failed["order"]["id"], {"scheduled_delivery_date": future()}
    )
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "PENDING"
    assert body["assigned_agent_id"] is None


def test_agent_or_admin_cannot_use_customer_reschedule_endpoint(
    client, db_session, pricing_world, admin_headers, failed_order
):
    failed = failed_order
    assert (
        client.post(
            f"/orders/{failed['order']['id']}/reschedule",
            json={"scheduled_delivery_date": future()},
            headers=admin_headers,
        ).status_code
        == status.HTTP_403_FORBIDDEN
    )
    assert (
        client.post(
            f"/orders/{failed['order']['id']}/reschedule",
            json={"scheduled_delivery_date": future()},
            headers=failed["agent"]["headers"],
        ).status_code
        == status.HTTP_403_FORBIDDEN
    )


def test_admin_reschedule_still_records_audit_row_without_attempt_bump(
    client, db_session, pricing_world, admin_headers, failed_order
):
    """Admin path keeps prior semantics: no fresh attempt counted, role recorded as ADMIN."""
    failed = failed_order
    attempts_before = client.get(
        f"/orders/{failed['order']['id']}", headers=admin_headers
    ).json()["delivery_attempt"]
    response = client.post(
        f"/admin/orders/{failed['order']['id']}/reschedule", json={}, headers=admin_headers
    )
    assert response.status_code == 200
    body = response.json()
    assert body["delivery_attempt"] == attempts_before

    row = db_session.scalar(select(Reschedule).where(Reschedule.order_id == failed["order"]["id"]))
    assert row is not None
    assert row.requested_by_role == "ADMIN"
