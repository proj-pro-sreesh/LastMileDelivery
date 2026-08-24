from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import CODRate, RateCard
from app.services.zone_service import DuplicateError, NotFoundError


def _integrity_conflict(detail: str) -> Exception:
    return DuplicateError(detail)


def list_rate_cards(db: Session) -> list[RateCard]:
    return list(db.scalars(select(RateCard).order_by(RateCard.order_type, RateCard.from_zone_id)))


def get_rate_card(db: Session, rate_card_id) -> RateCard | None:
    return db.get(RateCard, rate_card_id)


def create_rate_card(db: Session, **fields) -> RateCard:
    card = RateCard(**fields)
    db.add(card)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise _integrity_conflict(
            "A rate card already exists for this order type and zone pair"
        ) from exc
    db.refresh(card)
    return card


def update_rate_card(db: Session, rate_card_id, fields: dict) -> RateCard:
    card = db.get(RateCard, rate_card_id)
    if card is None:
        raise NotFoundError("Rate card not found")
    for key, value in fields.items():
        setattr(card, key, value)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise _integrity_conflict(
            "A rate card already exists for this order type and zone pair"
        ) from exc
    db.refresh(card)
    return card


def delete_rate_card(db: Session, rate_card_id) -> None:
    card = db.get(RateCard, rate_card_id)
    if card is None:
        raise NotFoundError("Rate card not found")
    db.delete(card)
    db.commit()


def list_cod_rates(db: Session) -> list[CODRate]:
    return list(db.scalars(select(CODRate).order_by(CODRate.order_type)))


def get_cod_rate(db: Session, cod_rate_id) -> CODRate | None:
    return db.get(CODRate, cod_rate_id)


def create_cod_rate(db: Session, *, order_type: str, surcharge) -> CODRate:
    rate = CODRate(order_type=order_type, surcharge=surcharge)
    db.add(rate)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise _integrity_conflict(f"A COD rate for {order_type} already exists") from exc
    db.refresh(rate)
    return rate


def update_cod_rate(db: Session, cod_rate_id, fields: dict) -> CODRate:
    rate = db.get(CODRate, cod_rate_id)
    if rate is None:
        raise NotFoundError("COD rate not found")
    for key, value in fields.items():
        setattr(rate, key, value)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise _integrity_conflict(f"A COD rate for {fields.get('order_type')} already exists") from exc
    db.refresh(rate)
    return rate


def delete_cod_rate(db: Session, cod_rate_id) -> None:
    rate = db.get(CODRate, cod_rate_id)
    if rate is None:
        raise NotFoundError("COD rate not found")
    db.delete(rate)
    db.commit()
