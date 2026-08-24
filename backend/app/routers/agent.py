from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_user, require_role
from app.models import User, UserRole
from app.models.enums import OrderStatus
from app.schemas.orders import OrderResponse
from app.schemas.status import AgentStatusUpdateRequest
from app.services import order_service
from app.services.state_machine import InvalidTransitionError, validate_agent_transition

router = APIRouter(prefix="/agent", tags=["agent"], dependencies=[Depends(require_role(UserRole.AGENT))])


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
