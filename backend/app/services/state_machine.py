from app.models.enums import OrderStatus

ALLOWED_TRANSITIONS: dict[OrderStatus, set[OrderStatus]] = {
    OrderStatus.PENDING: {OrderStatus.ASSIGNED, OrderStatus.CANCELLED},
    OrderStatus.ASSIGNED: {OrderStatus.PICKED_UP, OrderStatus.CANCELLED},
    OrderStatus.PICKED_UP: {OrderStatus.IN_TRANSIT},
    OrderStatus.IN_TRANSIT: {OrderStatus.OUT_FOR_DELIVERY},
    OrderStatus.OUT_FOR_DELIVERY: {OrderStatus.DELIVERED, OrderStatus.FAILED},
    OrderStatus.DELIVERED: set(),
    # FAILED -> PENDING happens ONLY through the customer reschedule flow (Phase 7).
    OrderStatus.FAILED: {OrderStatus.PENDING},
    OrderStatus.CANCELLED: set(),
}

AGENT_ALLOWED_EDGES: set[tuple[OrderStatus, OrderStatus]] = {
    (OrderStatus.ASSIGNED, OrderStatus.PICKED_UP),
    (OrderStatus.PICKED_UP, OrderStatus.IN_TRANSIT),
    (OrderStatus.IN_TRANSIT, OrderStatus.OUT_FOR_DELIVERY),
    (OrderStatus.OUT_FOR_DELIVERY, OrderStatus.DELIVERED),
    (OrderStatus.OUT_FOR_DELIVERY, OrderStatus.FAILED),
}


class InvalidTransitionError(Exception):
    pass


def validate_agent_transition(current: OrderStatus, target: OrderStatus) -> None:
    if current == target or (current, target) not in AGENT_ALLOWED_EDGES:
        raise InvalidTransitionError(f"Agents cannot move an order from {current.value} to {target.value}")


def validate_admin_override(current: OrderStatus, target: OrderStatus) -> None:
    if current == target:
        raise InvalidTransitionError(f"Order is already in status {current.value}")
    if current == OrderStatus.FAILED and target == OrderStatus.PENDING:
        raise InvalidTransitionError(
            "FAILED orders must be rescheduled via POST /admin/orders/{id}/reschedule"
        )
