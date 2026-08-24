"""Phase 8: notifications — in-app feed on order events, mock email/SMS, read state."""

import pytest
from fastapi import status

from app.models import UserRole
from tests.test_assignment import auto_assign, make_agent
from tests.test_lifecycle import agent_update
from tests.test_orders import create_order as api_create_order


@pytest.fixture
def assigned(client, db_session, pricing_world, customer_headers, admin_headers):
    """Order created and assigned to a fresh agent; returns both header sets + ids."""
    agent = make_agent(db_session, lat="13.083000", lng="80.271000", zone_code="CHE-CEN")
    order = api_create_order(client, customer_headers).json()
    assert client.post(
        f"/admin/orders/{order['id']}/assign", json={"agent_id": agent["id"]}, headers=admin_headers
    ).status_code == 200
    return {"order": order, "agent": agent}


def kinds(client, headers):
    return [n["kind"] for n in client.get("/notifications", headers=headers).json()]


def test_assignment_notifies_customer_and_agent(client, customer_headers, assigned):
    customer_feed = client.get("/notifications", headers=customer_headers).json()
    assert any(n["kind"] == "order.assigned" and n["order_id"] == assigned["order"]["id"] for n in customer_feed)

    agent_feed = client.get("/notifications", headers=assigned["agent"]["headers"]).json()
    assert any(n["kind"] == "assignment.new" for n in agent_feed)


def test_status_changes_generate_customer_notifications(client, customer_headers, assigned):
    oid = assigned["order"]["id"]
    ah = assigned["agent"]["headers"]
    for step in ["PICKED_UP", "IN_TRANSIT", "OUT_FOR_DELIVERY", "DELIVERED"]:
        assert agent_update(client, ah, oid, step).status_code == 200

    assert kinds(client, customer_headers) == [
        "order.delivered",
        "order.out_for_delivery",
        "order.in_transit",
        "order.picked_up",
        "order.assigned",
    ]


def test_failed_notification_includes_reason_then_redelivery_notice(
    client, db_session, pricing_world, customer_headers, admin_headers, assigned
):
    # fixture leaves order ASSIGNED; walk to OUT_FOR_DELIVERY first
    oid = assigned["order"]["id"]
    ah = assigned["agent"]["headers"]
    for step in ["PICKED_UP", "IN_TRANSIT", "OUT_FOR_DELIVERY"]:
        assert agent_update(client, ah, oid, step).status_code == 200
    assert agent_update(client, ah, oid, "FAILED", remarks="Customer not home").status_code == 200

    failed = next(
        n for n in client.get("/notifications", headers=customer_headers).json() if n["kind"] == "order.failed"
    )
    assert "Customer not home" in failed["message"]

    resched = client.post(f"/admin/orders/{oid}/reschedule", json={}, headers=admin_headers)
    assert resched.status_code == 200
    latest = client.get("/notifications", headers=customer_headers).json()[0]
    assert latest["kind"] == "order.pending"
    assert "rescheduled" in latest["message"].lower()


def test_cancellation_notifies_customer(client, db_session, pricing_world, customer_headers, admin_headers):
    order = api_create_order(client, customer_headers).json()
    response = client.patch(
        f"/admin/orders/{order['id']}/status",
        json={"status": "CANCELLED", "remarks": "Duplicate booking"},
        headers=admin_headers,
    )
    assert response.status_code == 200
    assert kinds(client, customer_headers)[0] == "order.cancelled"


def test_feed_scoping_and_auth(client, db_session, pricing_world, make_auth_headers, customer_headers, admin_headers):
    other_customer = make_auth_headers(UserRole.CUSTOMER, name="Other")
    order = api_create_order(client, customer_headers).json()
    client.patch(
        f"/admin/orders/{order['id']}/status",
        json={"status": "CANCELLED", "remarks": "Duplicate booking"},
        headers=admin_headers,
    )

    mine = kinds(client, customer_headers)
    theirs = kinds(client, other_customer)
    assert "order.cancelled" in mine
    assert theirs == []

    assert client.get("/notifications").status_code == status.HTTP_401_UNAUTHORIZED


def test_mark_read_flow(client, pricing_world, customer_headers, admin_headers):
    order = api_create_order(client, customer_headers).json()
    client.patch(
        f"/admin/orders/{order['id']}/status",
        json={"status": "CANCELLED", "remarks": "Duplicate booking"},
        headers=admin_headers,
    )
    notification_id = client.get("/notifications?unread=true", headers=customer_headers).json()[0]["id"]

    marked = client.post(f"/notifications/{notification_id}/read", headers=customer_headers)
    assert marked.status_code == 200
    assert marked.json()["read_at"] is not None

    assert client.get("/notifications?unread=true", headers=customer_headers).json() == []
    assert all(n["read_at"] is not None for n in client.get("/notifications", headers=customer_headers).json())


def test_cannot_mark_someone_elses_notification(
    client, db_session, pricing_world, make_auth_headers, customer_headers, admin_headers
):
    stranger = make_auth_headers(UserRole.CUSTOMER, name="Stranger")
    order = api_create_order(client, customer_headers).json()
    client.patch(
        f"/admin/orders/{order['id']}/status",
        json={"status": "CANCELLED", "remarks": "Duplicate booking"},
        headers=admin_headers,
    )
    foreign_id = client.get("/notifications", headers=customer_headers).json()[0]["id"]

    assert (
        client.post(f"/notifications/{foreign_id}/read", headers=stranger).status_code
        == status.HTTP_404_NOT_FOUND
    )


def test_mark_all_read(client, pricing_world, customer_headers, admin_headers):
    for _ in range(3):
        order = api_create_order(client, customer_headers).json()
        client.patch(
            f"/admin/orders/{order['id']}/status",
            json={"status": "CANCELLED", "remarks": "Bulk cleanup"},
            headers=admin_headers,
        )
    assert len(client.get("/notifications?unread=true", headers=customer_headers).json()) >= 3

    assert client.post("/notifications/read-all", headers=customer_headers).status_code == 204
    assert client.get("/notifications?unread=true", headers=customer_headers).json() == []


def test_disabled_mode_skips_notifications(client, monkeypatch, db_session, pricing_world, customer_headers, admin_headers):
    from app.core.config import get_settings
    from app.services import notification_service

    monkeypatch.setattr(type(get_settings()), "notifications_enabled", property(lambda self: False))

    order = api_create_order(client, customer_headers).json()
    created = notification_service.notify(
        db_session, recipient_id=None or order["customer_id"], kind="test", title="t", message="m"
    )
    assert created == []
