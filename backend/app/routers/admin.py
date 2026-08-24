import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import require_role
from app.models.user import UserRole
from app.schemas.orders import OrderResponse
from app.schemas.pricing import (
    CODRateCreate,
    CODRateResponse,
    CODRateUpdate,
    RateCardCreate,
    RateCardResponse,
    RateCardUpdate,
)
from app.schemas.status import AdminStatusOverrideRequest
from app.schemas.zones import AreaCreate, AreaResponse, AreaUpdate, ZoneCreate, ZoneResponse, ZoneUpdate
from app.services import order_service, pricing_service, zone_service
from app.services.state_machine import InvalidTransitionError, validate_admin_override
from app.services.zone_service import DuplicateError, NotFoundError

router = APIRouter(prefix="/admin", tags=["admin"], dependencies=[Depends(require_role(UserRole.ADMIN))])


@router.patch("/orders/{order_id}/status", response_model=OrderResponse)
def override_order_status(
    order_id: uuid.UUID,
    payload: AdminStatusOverrideRequest,
    db: Session = Depends(get_db),
    current_user=Depends(require_role(UserRole.ADMIN)),
):
    order = order_service.get_order(db, order_id)
    if order is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found")
    try:
        validate_admin_override(order.status, payload.status)
    except InvalidTransitionError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc

    return order_service.update_status(
        db, order=order, new_status=payload.status, actor_id=current_user.id, remarks=payload.remarks
    )


@router.post("/zones", response_model=ZoneResponse, status_code=status.HTTP_201_CREATED)
def create_zone(payload: ZoneCreate, db: Session = Depends(get_db)):
    try:
        return zone_service.create_zone(db, name=payload.name, code=payload.code)
    except DuplicateError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc


@router.get("/zones", response_model=list[ZoneResponse])
def list_zones(db: Session = Depends(get_db)):
    return zone_service.list_zones(db)


@router.put("/zones/{zone_id}", response_model=ZoneResponse)
def update_zone(zone_id: uuid.UUID, payload: ZoneUpdate, db: Session = Depends(get_db)):
    try:
        return zone_service.update_zone(db, zone_id, **payload.model_dump(exclude_none=True))
    except NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except DuplicateError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc


@router.delete("/zones/{zone_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_zone(zone_id: uuid.UUID, db: Session = Depends(get_db)):
    try:
        zone_service.delete_zone(db, zone_id)
    except NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except DuplicateError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/areas", response_model=AreaResponse, status_code=status.HTTP_201_CREATED)
def create_area(payload: AreaCreate, db: Session = Depends(get_db)):
    try:
        return zone_service.create_area(db, name=payload.name, pincode=payload.pincode, zone_id=payload.zone_id)
    except NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except DuplicateError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc


@router.get("/areas", response_model=list[AreaResponse])
def list_areas(
    db: Session = Depends(get_db),
    zone_id: uuid.UUID | None = Query(default=None),
):
    return zone_service.list_areas(db, zone_id=zone_id)


@router.put("/areas/{area_id}", response_model=AreaResponse)
def update_area(area_id: uuid.UUID, payload: AreaUpdate, db: Session = Depends(get_db)):
    try:
        return zone_service.update_area(db, area_id, **payload.model_dump(exclude_none=True))
    except NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except DuplicateError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc


@router.delete("/areas/{area_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_area(area_id: uuid.UUID, db: Session = Depends(get_db)):
    try:
        zone_service.delete_area(db, area_id)
    except NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/rates", response_model=RateCardResponse, status_code=status.HTTP_201_CREATED)
def create_rate_card(payload: RateCardCreate, db: Session = Depends(get_db)):
    try:
        return pricing_service.create_rate_card(db, **payload.model_dump(mode="json"))
    except DuplicateError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc


@router.get("/rates", response_model=list[RateCardResponse])
def list_rate_cards(db: Session = Depends(get_db)):
    return pricing_service.list_rate_cards(db)


@router.put("/rates/{rate_card_id}", response_model=RateCardResponse)
def update_rate_card(rate_card_id: uuid.UUID, payload: RateCardUpdate, db: Session = Depends(get_db)):
    try:
        return pricing_service.update_rate_card(db, rate_card_id, payload.model_dump(exclude_none=True, mode="json"))
    except NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except DuplicateError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc


@router.delete("/rates/{rate_card_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_rate_card(rate_card_id: uuid.UUID, db: Session = Depends(get_db)):
    try:
        pricing_service.delete_rate_card(db, rate_card_id)
    except NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/cod-rates", response_model=CODRateResponse, status_code=status.HTTP_201_CREATED)
def create_cod_rate(payload: CODRateCreate, db: Session = Depends(get_db)):
    try:
        return pricing_service.create_cod_rate(db, order_type=payload.order_type.value, surcharge=payload.surcharge)
    except DuplicateError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc


@router.get("/cod-rates", response_model=list[CODRateResponse])
def list_cod_rates(db: Session = Depends(get_db)):
    return pricing_service.list_cod_rates(db)


@router.put("/cod-rates/{cod_rate_id}", response_model=CODRateResponse)
def update_cod_rate(cod_rate_id: uuid.UUID, payload: CODRateUpdate, db: Session = Depends(get_db)):
    try:
        fields = payload.model_dump(exclude_none=True)
        if "order_type" in fields:
            fields["order_type"] = fields["order_type"].value
        return pricing_service.update_cod_rate(db, cod_rate_id, fields)
    except NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except DuplicateError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc


@router.delete("/cod-rates/{cod_rate_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_cod_rate(cod_rate_id: uuid.UUID, db: Session = Depends(get_db)):
    try:
        pricing_service.delete_cod_rate(db, cod_rate_id)
    except NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return Response(status_code=status.HTTP_204_NO_CONTENT)
