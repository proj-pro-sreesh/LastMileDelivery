from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import OrderTracking, OrderStatus


def add_tracking_record(db: Session, *, order_id, status: OrderStatus, actor_id, remarks: str | None = None) -> OrderTracking:
    """Append a tracking row. The caller owns the transaction/commit."""
    record = OrderTracking(order_id=order_id, status=status, actor_id=actor_id, remarks=remarks)
    db.add(record)
    return record


def list_tracking(db: Session, order_id) -> list[OrderTracking]:
    return list(
        db.scalars(select(OrderTracking).where(OrderTracking.order_id == order_id).order_by(OrderTracking.created_at, OrderTracking.id))
    )
