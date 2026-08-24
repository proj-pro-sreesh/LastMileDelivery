from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_user, require_role
from app.models import User, UserRole
from app.models.enums import OrderStatus
from app.schemas.agent import AvailabilityUpdateRequest, LocationUpdateRequest
from app.schemas.orders import OrderResponse
from app.schemas.status import AgentStatusUpdateRequest
from app.services import assignment_service, order_service, zone_service
from app.services.state_machine import InvalidTransitionError, validate_agent_transition

router = APIRouter(prefix="/agent", tags=["agent"], dependencies=[Depends(require_role(UserRole.AGENT))])


@router.patch("/availability", response_model=AvailabilityUpdateRequest)
def set_availability(
    payload: AvailabilityUpdateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        assignment_service.update_availability(db, current_user, payload.availability_status)
    except assignment_service.AgentNotEligibleError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    return payload


@router.patch("/location")
def update_location(
    payload: LocationUpdateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if payload.pincode is not None:
        try:
            zone_service.get_zone_for_pincode(db, payload.pincode)
        except zone_service.PincodeNotMappedError as exc:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail=f"Pincode {payload.pincode} is not mapped to any configured area/zone",
            ) from exc

    profile = assignment_service.update_location(
        db,
        current_user,
        latitude=payload.latitude,
        longitude=payload.longitude,
        pincode=payload.pincode,
    )
    return {
        "latitude": profile.latitude,
        "longitude": profile.longitude,
        "current_zone_id": str(profile.current_zone_id) if profile.current_zone_id else None,
    }


@router.get("/orders", response_model=list[OrderResponse])
def my_assigned_orders(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    order_status: OrderStatus | None = Query(default=None, alias="status"),
):
    return order_service.list_orders_for_agent(db, current_user, status=order_status)


@router.patch("/orders/{order_id}/status", response_model=OrderResponse)
def update_order_status(
    order_id: UUID,
    payload: AgentStatusUpdateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    order = order_service.get_order_for_agent(db, current_user, order_id)
    if order is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Assigned order not found")

    try:
        validate_agent_transition(order.status, payload.status)
    except InvalidTransitionError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc

    if payload.status == OrderStatus.FAILED and not (payload.remarks or "").strip():
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="A failure reason is required when marking a delivery as failed",
        )

    return order_service.update_status(
        db, order=order, new_status=payload.status, actor_id=current_user.id, remarks=payload.remarks
    )
