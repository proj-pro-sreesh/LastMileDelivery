from datetime import date, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Area, Order, OrderStatus, User, UserRole
from app.models.enums import OrderType, PaymentType
from app.services import assignment_service, tracking_service
from app.services.rate_engine import calculate_quote


class CustomerNotFoundError(Exception):
    pass


def _default_delivery_date() -> date:
    return date.today() + timedelta(days=1)


def _area_for_pincode(db: Session, pincode: str) -> Area | None:
    return db.scalar(select(Area).where(Area.pincode == pincode.strip()))


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

    pickup_area = _area_for_pincode(db, pickup_pincode)
    drop_area = _area_for_pincode(db, drop_pincode)

    order = Order(
        customer_id=customer_id,
        pickup_address=pickup_address.strip(),
        pickup_pincode=pickup_pincode.strip(),
        pickup_zone_id=breakdown["pickup_zone"].id,
        pickup_latitude=pickup_area.latitude if pickup_area else None,
        pickup_longitude=pickup_area.longitude if pickup_area else None,
        drop_address=drop_address.strip(),
        drop_pincode=drop_pincode.strip(),
        drop_zone_id=breakdown["drop_zone"].id,
        drop_latitude=drop_area.latitude if drop_area else None,
        drop_longitude=drop_area.longitude if drop_area else None,
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


def get_order_for_agent(db: Session, agent: User, order_id) -> Order | None:
    order = db.get(Order, order_id)
    if order is None or order.assigned_agent_id != agent.id:
        return None
    return order


def list_orders_for_agent(db: Session, agent: User, *, status=None) -> list[Order]:
    query = select(Order).where(Order.assigned_agent_id == agent.id).order_by(Order.created_at.desc())
    if status is not None:
        query = query.where(Order.status == status)
    return list(db.scalars(query))


def update_status(db: Session, *, order: Order, new_status, actor_id, remarks: str | None = None) -> Order:
    """Apply a status change and append the immutable tracking row in one transaction."""
    order.status = new_status
    if new_status in assignment_service.TERMINAL_ORDER_STATUSES:
        assignment_service.release_agent_if_idle(db, order)
    tracking_service.add_tracking_record(db, order_id=order.id, status=new_status, actor_id=actor_id, remarks=remarks)
    db.commit()
    db.refresh(order)
    return order
