from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import AgentProfile, Order, User, UserRole
from app.models.enums import AvailabilityStatus, OrderStatus
from app.services import notification_service, tracking_service
from app.services.zone_service import PincodeNotMappedError, get_zone_for_pincode
from app.utils.geo import haversine_km

ACTIVE_ORDER_STATUSES = [
    OrderStatus.ASSIGNED,
    OrderStatus.PICKED_UP,
    OrderStatus.IN_TRANSIT,
    OrderStatus.OUT_FOR_DELIVERY,
]

TERMINAL_ORDER_STATUSES = {OrderStatus.DELIVERED, OrderStatus.FAILED, OrderStatus.CANCELLED}


class AgentNotFoundError(Exception):
    pass


class AgentNotEligibleError(Exception):
    pass


class OrderNotAssignableError(Exception):
    pass


def get_or_create_profile(db: Session, user_id) -> AgentProfile:
    profile = db.scalar(select(AgentProfile).where(AgentProfile.user_id == user_id))
    if profile is None:
        profile = AgentProfile(user_id=user_id, availability_status=AvailabilityStatus.AVAILABLE)
        db.add(profile)
        db.commit()
        db.refresh(profile)
    return profile


def update_availability(db: Session, agent_user: User, status: AvailabilityStatus) -> AgentProfile:
    if status == AvailabilityStatus.OFFLINE and _count_active_orders(db, agent_user.id) > 0:
        raise AgentNotEligibleError("Cannot go offline while you still have active assigned orders")
    profile = get_or_create_profile(db, agent_user.id)
    profile.availability_status = status
    db.commit()
    db.refresh(profile)
    return profile


def update_location(
    db: Session, agent_user: User, *, latitude=None, longitude=None, pincode: str | None = None
) -> AgentProfile:
    profile = get_or_create_profile(db, agent_user.id)
    if latitude is not None:
        profile.latitude = latitude
    if longitude is not None:
        profile.longitude = longitude
    if pincode is not None:
        try:
            profile.current_zone_id = get_zone_for_pincode(db, pincode).id
        except PincodeNotMappedError as exc:
            db.rollback()
            raise exc
    db.commit()
    db.refresh(profile)
    return profile


def _count_active_orders(db: Session, agent_user_id) -> int:
    return int(
        db.scalar(
            select(func.count())
            .select_from(Order)
            .where(Order.assigned_agent_id == agent_user_id, Order.status.in_(ACTIVE_ORDER_STATUSES))
        )
        or 0
    )


def list_agents_with_load(db: Session) -> list[dict]:
    active = _active_orders_subquery()
    rows = db.execute(
        select(User, AgentProfile, func.coalesce(active.c.active_orders, 0))
        .outerjoin(AgentProfile, AgentProfile.user_id == User.id)
        .outerjoin(active, active.c.agent_id == User.id)
        .where(User.role == UserRole.AGENT)
        .order_by(User.name)
    ).all()

    agents = []
    for user, profile, active_orders in rows:
        agents.append(
            {
                "user_id": user.id,
                "name": user.name,
                "email": user.email,
                "phone": user.phone,
                "availability_status": (
                    profile.availability_status if profile else AvailabilityStatus.AVAILABLE
                ),
                "latitude": profile.latitude if profile else None,
                "longitude": profile.longitude if profile else None,
                "current_zone_id": profile.current_zone_id if profile else None,
                "vehicle_type": profile.vehicle_type if profile else None,
                "active_orders": int(active_orders or 0),
            }
        )
    return agents


def _active_orders_subquery():
    return (
        select(Order.assigned_agent_id.label("agent_id"), func.count().label("active_orders"))
        .where(Order.status.in_(ACTIVE_ORDER_STATUSES))
        .group_by(Order.assigned_agent_id)
        .subquery()
    )


def _available_agent_profiles(db: Session) -> list[tuple[AgentProfile, str]]:
    return list(
        db.execute(
            select(AgentProfile, User.id)
            .join(User, User.id == AgentProfile.user_id)
            .where(User.role == UserRole.AGENT, AgentProfile.availability_status == AvailabilityStatus.AVAILABLE)
        ).all()
    )


def manual_assign(db: Session, *, order: Order, agent_user_id, actor_id) -> Order:
    agent_user = db.get(User, agent_user_id)
    if agent_user is None or agent_user.role != UserRole.AGENT:
        raise AgentNotFoundError("Agent not found")
    if order.status != OrderStatus.PENDING:
        raise OrderNotAssignableError(f"Order is in status {order.status.value}; only PENDING orders can be assigned")

    profile = get_or_create_profile(db, agent_user.id)
    if profile.availability_status != AvailabilityStatus.AVAILABLE:
        raise AgentNotEligibleError(f"Agent is {profile.availability_status.value} and cannot take new orders")

    _apply_assignment(db, order=order, profile=profile, actor_id=actor_id, remarks="Assigned by admin")
    return order


def auto_assign(db: Session, *, order: Order, actor_id) -> tuple[bool, str | None]:
    """Deterministically assign the nearest AVAILABLE agent; returns (assigned, message).

    Preference order: pickup-zone agents first, then Haversine distance to the
    pickup coordinates; agents without coordinates sort last; ties broken by user id.
    """
    if order.status != OrderStatus.PENDING:
        raise OrderNotAssignableError(f"Order is in status {order.status.value}; only PENDING orders can be assigned")

    candidates = []
    for profile, _user_id in _available_agent_profiles(db):
        candidates.append(profile)

    if not candidates:
        return False, "No available agents right now; order remains PENDING"

    def sort_key(profile: AgentProfile):
        in_pickup_zone = profile.current_zone_id == order.pickup_zone_id
        if profile.latitude is not None and profile.longitude is not None and order.pickup_latitude and order.pickup_longitude:
            distance = haversine_km(
                float(profile.latitude),
                float(profile.longitude),
                float(order.pickup_latitude),
                float(order.pickup_longitude),
            )
        else:
            distance = float("inf")
        return (not in_pickup_zone, distance, str(profile.user_id))

    winner = min(candidates, key=sort_key)
    _apply_assignment(
        db,
        order=order,
        profile=winner,
        actor_id=actor_id,
        remarks="Auto-assigned nearest available agent",
    )
    return True, f"Assigned to agent {winner.user_id}"


def _apply_assignment(db: Session, *, order: Order, profile: AgentProfile, actor_id, remarks: str) -> None:
    order.assigned_agent_id = profile.user_id
    order.status = OrderStatus.ASSIGNED
    profile.availability_status = AvailabilityStatus.BUSY
    tracking_service.add_tracking_record(
        db, order_id=order.id, status=OrderStatus.ASSIGNED, actor_id=actor_id, remarks=remarks
    )
    notification_service.notify_order_status(db, order=order, new_status=OrderStatus.ASSIGNED)
    notification_service.notify_agent_assigned(db, order=order, agent_user_id=profile.user_id)
    db.commit()
    db.refresh(order)


def release_agent_if_idle(db: Session, order: Order) -> None:
    """When an assigned order reaches a terminal state, free the agent unless they hold other active orders.

    Must be called inside the caller's transaction (before commit).
    """
    if order.assigned_agent_id is None:
        return
    remaining_active = _count_active_orders_excluding(db, order.assigned_agent_id, exclude_order_id=order.id)
    if remaining_active > 0:
        return
    profile = db.scalar(select(AgentProfile).where(AgentProfile.user_id == order.assigned_agent_id))
    if profile is not None and profile.availability_status == AvailabilityStatus.BUSY:
        profile.availability_status = AvailabilityStatus.AVAILABLE


def _count_active_orders_excluding(db: Session, agent_user_id, *, exclude_order_id) -> int:
    return int(
        db.scalar(
            select(func.count())
            .select_from(Order)
            .where(
                Order.assigned_agent_id == agent_user_id,
                Order.status.in_(ACTIVE_ORDER_STATUSES),
                Order.id != exclude_order_id,
            )
        )
        or 0
    )
