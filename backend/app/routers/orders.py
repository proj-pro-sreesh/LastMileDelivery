import uuid
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_user, require_role
from app.models import User, UserRole
from app.models.enums import OrderStatus
from app.schemas.orders import OrderCreateRequest, OrderResponse, TrackingEntryResponse
from app.schemas.pricing import QuoteRequest, QuoteResponse
from app.schemas.zones import ZoneResponse
from app.schemas.status import RescheduleRequest
from app.services import assignment_service, order_service, tracking_service
from app.services.rate_engine import CODRateNotFoundError, RateCardNotFoundError, calculate_quote
from app.services.zone_service import PincodeNotMappedError

router = APIRouter(tags=["orders"])

_PRICING_ERRORS = (PincodeNotMappedError, RateCardNotFoundError, CODRateNotFoundError)


def _quote_response(db: Session, payload: QuoteRequest) -> QuoteResponse:
    breakdown = calculate_quote(db, **payload.model_dump())
    return QuoteResponse(
        pickup_zone=ZoneResponse.model_validate(breakdown["pickup_zone"]),
        drop_zone=ZoneResponse.model_validate(breakdown["drop_zone"]),
        zone_type=breakdown["zone_type"],
        actual_weight=breakdown["actual_weight"],
        volumetric_weight=breakdown["volumetric_weight"],
        chargeable_weight=breakdown["chargeable_weight"],
        rate_per_kg=breakdown["rate_per_kg"],
        minimum_charge_applied=breakdown["minimum_charge_applied"],
        base_charge=breakdown["base_charge"],
        cod_surcharge=breakdown["cod_surcharge"],
        total_charge=breakdown["total_charge"],
    )


@router.post("/orders/quote", response_model=QuoteResponse)
def get_quote(
    payload: QuoteRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.CUSTOMER, UserRole.ADMIN)),
):
    try:
        return _quote_response(db, payload)
    except _PRICING_ERRORS as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)) from exc


@router.post("/orders", response_model=OrderResponse, status_code=status.HTTP_201_CREATED)
def create_order(
    payload: OrderCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.CUSTOMER, UserRole.ADMIN)),
):
    customer_id = current_user.id
    if payload.customer_id is not None and payload.customer_id != current_user.id:
        if current_user.role != UserRole.ADMIN:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only admins can create orders on behalf of other customers",
            )
        customer = db.get(User, payload.customer_id)
        if customer is None or customer.role != UserRole.CUSTOMER:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Customer not found")
        customer_id = customer.id

    if payload.scheduled_delivery_date is not None and payload.scheduled_delivery_date < date.today():
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Scheduled delivery date cannot be in the past",
        )

    try:
        return order_service.create_order(db, customer_id=customer_id, actor_id=current_user.id, **payload.model_dump(exclude={"customer_id"}))
    except _PRICING_ERRORS as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)) from exc


@router.get("/orders", response_model=list[OrderResponse])
def list_orders(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    order_status: OrderStatus | None = Query(default=None, alias="status"),
    customer_id: uuid.UUID | None = Query(default=None),
    zone_id: uuid.UUID | None = Query(default=None),
    agent_id: uuid.UUID | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
):
    # zone/agent filters are admin-only operational views.
    if (zone_id is not None or agent_id is not None) and current_user.role != UserRole.ADMIN:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only admins can filter by zone or agent")
    target_customer = current_user.id
    if current_user.role == UserRole.ADMIN:
        target_customer = customer_id  # None -> all customers
    elif customer_id is not None and customer_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Customers can only view their own orders")
    return order_service.list_orders(
        db,
        customer_id=target_customer,
        status=order_status,
        zone_id=zone_id if current_user.role == UserRole.ADMIN else None,
        agent_id=agent_id if current_user.role == UserRole.ADMIN else None,
        limit=limit,
        offset=offset,
    )


def _get_order_for_user(order_id: uuid.UUID, user: User, db: Session):
    order = order_service.get_order(db, order_id)
    if order is None or not order_service.can_view(user, order):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found")
    return order


@router.get("/orders/{order_id}", response_model=OrderResponse)
def get_order(
    order_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return _get_order_for_user(order_id, current_user, db)


@router.get("/orders/{order_id}/tracking", response_model=list[TrackingEntryResponse])
def get_order_tracking(
    order_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _get_order_for_user(order_id, current_user, db)
    return tracking_service.list_tracking(db, order_id)


@router.post("/orders/{order_id}/reschedule", response_model=OrderResponse)
def reschedule_my_order(
    order_id: uuid.UUID,
    payload: RescheduleRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.CUSTOMER)),
):
    """Customer-owned redelivery scheduling for a FAILED order (owner only)."""
    order = order_service.get_order(db, order_id)
    if order is None or order.customer_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found")
    if payload.scheduled_delivery_date is not None and payload.scheduled_delivery_date < date.today():
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="scheduled_delivery_date cannot be in the past",
        )
    try:
        order = order_service.reschedule_order(
            db,
            order=order,
            actor_id=current_user.id,
            actor_role=UserRole.CUSTOMER.value,
            scheduled_delivery_date=payload.scheduled_delivery_date,
            remarks=payload.remarks,
        )
    except order_service.OrderNotReschedulableError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc

    # Schedule the retry attempt with the existing assignment engine — the nearest
    # AVAILABLE agent wins; the previous agent is never special-cased.
    assignment_service.auto_assign(db, order=order, actor_id=current_user.id)
    db.refresh(order)
    return order
