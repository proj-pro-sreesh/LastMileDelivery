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
    email_body: str | None = None,
) -> list[Notification]:
    """Record an in-app notification and dispatch email/SMS through the configured providers.

    Returns the created rows (empty list when notifications are disabled).
    Joins the caller's transaction — commit stays with the caller. Persistence and
    outbound delivery are failure-isolated: a provider error (or insert error) is
    logged and never rolls back the caller's transaction.
    """
    settings = get_settings()
    if not settings.notifications_enabled:
        return []

    user = db.get(User, recipient_id)
    email = user.email if user else "unknown"
    phone = user.phone if user else None

    # SAVEPOINT: if the insert fails the caller's transaction stays usable.
    nested = db.begin_nested()
    try:
        row = Notification(
            user_id=recipient_id,
            order_id=order_id,
            channel=NotificationChannel.IN_APP,
            kind=kind,
            title=title,
            message=message,
        )
        db.add(row)
        nested.commit()
    except Exception:
        nested.rollback()
        logger.exception("Failed to persist in-app notification for user=%s kind=%s", recipient_id, kind)
        row = None

    # Failure isolation: neither channel may ever break the caller's transaction.
    try:
        _dispatch_email(settings, to=email, subject=title, body=email_body or message)
    except Exception as exc:
        logger.error("Email dispatch crashed: %s", exc)
    try:
        _dispatch_sms(settings, to_phone=phone, text=f"{title}: {message}")
    except Exception as exc:
        logger.error("SMS dispatch crashed: %s", exc)
    return [row] if row is not None else []


def _dispatch_email(settings, *, to: str, subject: str, body: str) -> None:
    from app.services.providers.email import get_email_provider

    try:
        provider = get_email_provider(
            provider_name=settings.email_provider.lower(),
            api_key=settings.email_api_key,
            from_address=settings.email_from,
        )
        provider.send(to=to, subject=subject, body=body)
    except Exception as exc:  # delivery must never break order flows
        logger.error("Email delivery failed via %s: %s", settings.email_provider, exc)


def _dispatch_sms(settings, *, to_phone: str | None, text: str) -> None:
    from app.services.providers.sms import get_sms_provider

    try:
        provider = get_sms_provider(
            provider_name=settings.sms_provider.lower(),
            api_key=settings.sms_api_key,
            from_number=settings.sms_from,
        )
        provider.send(to_phone=to_phone or "", text=text)
    except Exception as exc:  # delivery must never break order flows
        logger.error("SMS delivery failed via %s: %s", settings.sms_provider, exc)


def _order_email_body(order, new_status: OrderStatus, message: str) -> str:
    """Richer email copy: in-app keeps the short message, email adds order context."""
    return (
        f"{message}\n\n"
        f"Order: {str(order.id)[:8]}\n"
        f"Status: {new_status.value}\n"
        f"Route: {order.pickup_pincode} → {order.drop_pincode}\n"
        f"Scheduled delivery: {order.scheduled_delivery_date or 'to be confirmed'}\n"
        f"Track this order in your dashboard."
    )


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
        email_body=_order_email_body(order, new_status, message),
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
