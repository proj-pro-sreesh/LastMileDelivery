from datetime import date, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Order, OrderStatus, User, UserRole
from app.models.enums import OrderType, PaymentType
from app.services import tracking_service
from app.services.rate_engine import calculate_quote


class CustomerNotFoundError(Exception):
    pass


def _default_delivery_date() -> date:
    return date.today() + timedelta(days=1)


def create_order(
    db: Session,
    *,
    customer_id,
    actor_id,
    pickup_address: str,
    pickup_pincode: str,
    drop_address: str,
    drop_pincode: str,
    length_cm,
    breadth_cm,
    height_cm,
    actual_weight_kg,
    order_type: OrderType,
    payment_type: PaymentType,
    scheduled_delivery_date: date | None = None,
) -> Order:
    breakdown = calculate_quote(
        db,
        pickup_pincode=pickup_pincode,
        drop_pincode=drop_pincode,
        length_cm=length_cm,
        breadth_cm=breadth_cm,
        height_cm=height_cm,
        actual_weight_kg=actual_weight_kg,
        order_type=order_type,
        payment_type=payment_type,
    )

    order = Order(
        customer_id=customer_id,
        pickup_address=pickup_address.strip(),
        pickup_pincode=pickup_pincode.strip(),
        pickup_zone_id=breakdown["pickup_zone"].id,
        drop_address=drop_address.strip(),
        drop_pincode=drop_pincode.strip(),
        drop_zone_id=breakdown["drop_zone"].id,
        length_cm=length_cm,
        breadth_cm=breadth_cm,
        height_cm=height_cm,
        actual_weight_kg=actual_weight_kg,
        volumetric_weight_kg=breakdown["volumetric_weight"],
        chargeable_weight_kg=breakdown["chargeable_weight"],
        order_type=order_type.value,
        payment_type=payment_type.value,
        base_charge=breakdown["base_charge"],
        cod_surcharge=breakdown["cod_surcharge"],
        total_charge=breakdown["total_charge"],
        status=OrderStatus.PENDING,
        delivery_attempt=1,
        scheduled_delivery_date=scheduled_delivery_date or _default_delivery_date(),
    )
    db.add(order)
    db.flush()

    tracking_service.add_tracking_record(
        db, order_id=order.id, status=OrderStatus.PENDING, actor_id=actor_id,
        remarks="Order created",
    )
    db.commit()
    db.refresh(order)
    return order


def get_order(db: Session, order_id) -> Order | None:
    return db.get(Order, order_id)


def list_orders(db: Session, *, customer_id=None, status: OrderStatus | None = None, limit: int = 50, offset: int = 0) -> list[Order]:
    query = select(Order).order_by(Order.created_at.desc()).limit(limit).offset(offset)
    if customer_id is not None:
        query = query.where(Order.customer_id == customer_id)
    if status is not None:
        query = query.where(Order.status == status)
    return list(db.scalars(query))


def can_view(user: User, order: Order) -> bool:
    """Admins see everything; customers only their own; agents only orders assigned to them."""
    if user.role == UserRole.ADMIN:
        return True
    if user.role == UserRole.CUSTOMER:
        return order.customer_id == user.id
    if user.role == UserRole.AGENT:
        return order.assigned_agent_id == user.id
    return False
