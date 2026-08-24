from decimal import ROUND_HALF_UP, Decimal
import math

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import CODRate, RateCard, Zone
from app.models.enums import OrderType, PaymentType, ZoneType
from app.services.zone_service import PincodeNotMappedError, get_zone_for_pincode

VOLUMETRIC_DIVISOR = Decimal("5000")


class RateCardNotFoundError(Exception):
    def __init__(self, order_type: str, pickup_zone: Zone, drop_zone: Zone):
        self.order_type = order_type
        super().__init__(
            f"No {order_type} rate card configured for "
            f"{pickup_zone.code} -> {drop_zone.code}"
        )


class CODRateNotFoundError(Exception):
    def __init__(self, order_type: str):
        super().__init__(f"No COD surcharge configured for order type {order_type}")


def _money(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def volumetric_weight(length_cm: Decimal, breadth_cm: Decimal, height_cm: Decimal) -> Decimal:
    """(L × B × H) / 5000 — cm and kg."""
    raw = (length_cm * breadth_cm * height_cm) / VOLUMETRIC_DIVISOR
    return _money(raw)


def chargeable_weight(actual_kg: Decimal, volumetric_kg: Decimal) -> Decimal:
    """max(actual, volumetric), rounded up to the whole kilogram (courier convention)."""
    return Decimal(math.ceil(max(actual_kg, volumetric_kg)))


def _order_type_value(order_type: "OrderType | str") -> str:
    return order_type.value if isinstance(order_type, OrderType) else str(order_type)


def find_rate_card(db: Session, *, order_type: "OrderType | str", from_zone_id, to_zone_id) -> RateCard | None:
    return db.scalar(
        select(RateCard).where(
            RateCard.order_type == _order_type_value(order_type),
            RateCard.from_zone_id == from_zone_id,
            RateCard.to_zone_id == to_zone_id,
        )
    )


def find_cod_surcharge(db: Session, order_type: "OrderType | str") -> CODRate | None:
    return db.scalar(select(CODRate).where(CODRate.order_type == _order_type_value(order_type)))


def calculate_quote(
    db: Session,
    *,
    pickup_pincode: str,
    drop_pincode: str,
    length_cm: Decimal,
    breadth_cm: Decimal,
    height_cm: Decimal,
    actual_weight_kg: Decimal,
    order_type: OrderType,
    payment_type: PaymentType,
) -> dict:
    pickup_zone = get_zone_for_pincode(db, pickup_pincode)
    drop_zone = get_zone_for_pincode(db, drop_pincode)

    volumetric = volumetric_weight(length_cm, breadth_cm, height_cm)
    chargeable = chargeable_weight(actual_weight_kg, volumetric)
    zone_type = ZoneType.INTRA_ZONE if pickup_zone.id == drop_zone.id else ZoneType.INTER_ZONE

    rate_card = find_rate_card(db, order_type=order_type, from_zone_id=pickup_zone.id, to_zone_id=drop_zone.id)
    if rate_card is None:
        raise RateCardNotFoundError(_order_type_value(order_type), pickup_zone, drop_zone)

    computed_charge = _money(rate_card.rate_per_kg * chargeable)
    minimum_applied = computed_charge < rate_card.minimum_charge
    base_charge = rate_card.minimum_charge if minimum_applied else computed_charge

    cod_surcharge = Decimal("0.00")
    if payment_type == PaymentType.COD:
        cod_rate = find_cod_surcharge(db, order_type)
        if cod_rate is None:
            raise CODRateNotFoundError(_order_type_value(order_type))
        cod_surcharge = cod_rate.surcharge

    total_charge = _money(base_charge + cod_surcharge)

    return {
        "pickup_zone": pickup_zone,
        "drop_zone": drop_zone,
        "zone_type": zone_type,
        "actual_weight": actual_weight_kg,
        "volumetric_weight": volumetric,
        "chargeable_weight": chargeable,
        "rate_per_kg": rate_card.rate_per_kg,
        "minimum_charge_applied": minimum_applied,
        "base_charge": base_charge,
        "cod_surcharge": cod_surcharge,
        "total_charge": total_charge,
    }
