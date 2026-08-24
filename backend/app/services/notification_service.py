import logging

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models import Notification, NotificationChannel, User
from app.models.enums import OrderStatus

logger = logging.getLogger("app.notifications")
if not logger.handlers:
    _handler = logging.StreamHandler()
    _handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s :: %(message)s"))
    logger.addHandler(_handler)
logger.setLevel(logging.INFO)

# Customer-facing copy for each order status change.
STATUS_TEMPLATES: dict[OrderStatus, tuple[str, str]] = {
    OrderStatus.ASSIGNED: (
        "Order assigned to a delivery agent",
        "Your order has been assigned to a delivery agent and will be picked up shortly.",
    ),
    OrderStatus.PICKED_UP: (
        "Parcel picked up",
        "Your parcel has been picked up by the delivery agent.",
    ),
    OrderStatus.IN_TRANSIT: (
        "Parcel in transit",
        "Your parcel is on its way to the destination hub.",
    ),
    OrderStatus.OUT_FOR_DELIVERY: (
        "Out for delivery",
        "Your parcel is out for delivery and should arrive today.",
    ),
    OrderStatus.DELIVERED: (
        "Delivered",
        "Your parcel has been delivered successfully.",
    ),
    OrderStatus.FAILED: (
        "Delivery attempt failed",
        "Delivery attempt failed. We will retry shortly.",  # reason appended when provided
    ),
    OrderStatus.CANCELLED: (
        "Order cancelled",
        "Your order has been cancelled.",
    ),
}


def notify(
    db: Session,
    *,
    recipient_id,
    kind: str,
    title: str,
    message: str,
    order_id=None,
) -> list[Notification]:
    """Record an in-app notification and simulate email/SMS delivery.

    Returns the created rows (empty list when notifications are disabled).
    Joins the caller's transaction — commit stays with the caller.
    """
    settings = get_settings()
    if not settings.notifications_enabled:
        return []

    user = db.get(User, recipient_id)
    email = user.email if user else "unknown"

    row = Notification(
        user_id=recipient_id,
        order_id=order_id,
        channel=NotificationChannel.IN_APP,
        kind=kind,
        title=title,
        message=message,
    )
    db.add(row)
    logger.info("[MOCK EMAIL] to=%s subject=%s body=%s", email, title, message)
    logger.info("[MOCK SMS] to_user=%s text=%s", recipient_id, title)
    return [row]


def notify_order_status(db: Session, *, order, new_status: OrderStatus, remarks: str | None = None) -> None:
    if new_status == OrderStatus.PENDING:  # only reachable via the reschedule flow
        title, message = "Redelivery scheduled", "Your order has been rescheduled for another delivery attempt."
    else:
        template = STATUS_TEMPLATES.get(new_status)
        if template is None:
            return
        title, message = template
        if new_status == OrderStatus.FAILED and remarks:
            message = f"{message} Reason: {remarks}"

    notify(
        db,
        recipient_id=order.customer_id,
        kind=f"order.{new_status.value.lower()}",
        title=title,
        message=message,
        order_id=order.id,
    )


def notify_agent_assigned(db: Session, *, order, agent_user_id) -> None:
    notify(
        db,
        recipient_id=agent_user_id,
        kind="assignment.new",
        title="New order assigned to you",
        message=(
            f"Order {str(order.id)[:8]} has been assigned to you. "
            f"Pickup pincode {order.pickup_pincode}, drop pincode {order.drop_pincode}."
        ),
        order_id=order.id,
    )


def list_for_user(db: Session, user_id, *, unread_only: bool = False, limit: int = 50) -> list[Notification]:
    query = select(Notification).where(Notification.user_id == user_id).order_by(Notification.created_at.desc())
    if unread_only:
        query = query.where(Notification.read_at.is_(None))
    return list(db.scalars(query.limit(limit)))


def mark_read(db: Session, user_id, notification_id) -> Notification | None:
    row = db.scalar(select(Notification).where(Notification.id == notification_id, Notification.user_id == user_id))
    if row is None:
        return None
    if row.read_at is None:
        row.read_at = func.now()
        db.commit()
        db.refresh(row)
    return row


def mark_all_read(db: Session, user_id) -> int:
    rows = list(
        db.scalars(select(Notification).where(Notification.user_id == user_id, Notification.read_at.is_(None)))
    )
    for row in rows:
        row.read_at = func.now()
    if rows:
        db.commit()
    return len(rows)
