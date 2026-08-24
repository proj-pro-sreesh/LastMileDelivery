import pytest
from sqlalchemy import delete

from app.models import Area, CODRate, RateCard, Zone
from app.services import rate_engine
from app.services.rate_engine import CODRateNotFoundError, RateCardNotFoundError
from app.services.zone_service import PincodeNotMappedError

from decimal import Decimal as D


@pytest.fixture
def pricing_world(db_session):
    """CHE-CEN (600001,600002), CHE-STH (600041), BLR-EST (560001) with seeded-equivalent rates."""
    che_cen = Zone(name="Chennai Central", code="CHE-CEN")
    che_sth = Zone(name="Chennai South", code="CHE-STH")
    blr_est = Zone(name="Bengaluru East", code="BLR-EST")
    db_session.add_all([che_cen, che_sth, blr_est])
    db_session.flush()

    for zone, pin in [(che_cen, "600001"), (che_cen, "600002"), (che_sth, "600041"), (blr_est, "560001")]:
        db_session.add(Area(name=f"Area {pin}", pincode=pin, zone_id=zone.id))

    rates = [
        ("B2B", True, "30.00", "80.00"),
        ("B2B", False, "45.00", "120.00"),
        ("B2C", True, "40.00", "100.00"),
        ("B2C", False, "60.00", "150.00"),
    ]
    for order_type, intra, rate, minimum in rates:
        for src in [che_cen, che_sth, blr_est]:
            targets = [src] if intra else [z for z in (che_cen, che_sth, blr_est) if z.id != src.id]
            for dst in targets:
                db_session.add(
                    RateCard(
                        order_type=order_type,
                        from_zone_id=src.id,
                        to_zone_id=dst.id,
                        rate_per_kg=rate,
                        minimum_charge=minimum,
                    )
                )

    db_session.add(CODRate(order_type="B2B", surcharge="25.00"))
    db_session.add(CODRate(order_type="B2C", surcharge="30.00"))
    db_session.commit()
    return {"che_cen": che_cen, "che_sth": che_sth, "blr_est": blr_est}


def quote(db, **overrides):
    payload = dict(
        pickup_pincode="600001",
        drop_pincode="600002",
        length_cm=D("50"),
        breadth_cm=D("40"),
        height_cm=D("30"),
        actual_weight_kg=D("8"),
        order_type="B2C",
        payment_type="COD",
    )
    payload.update(overrides)
    return rate_engine.calculate_quote(db, **payload)


def test_spec_example_b2c_intra_cod(pricing_world, db_session):
    result = quote(db_session)
    assert result["volumetric_weight"] == D("12.00")
    assert result["chargeable_weight"] == D("12")
    assert result["zone_type"] == "INTRA_ZONE"
    assert result["rate_per_kg"] == D("40.00")
    assert result["base_charge"] == D("480.00")
    assert result["cod_surcharge"] == D("30.00")
    assert result["total_charge"] == D("510.00")


def test_prepaid_has_no_surcharge(pricing_world, db_session):
    result = quote(db_session, payment_type="PREPAID")
    assert result["cod_surcharge"] == D("0.00")
    assert result["total_charge"] == result["base_charge"]


def test_b2b_inter_zone_uses_pair_card(pricing_world, db_session):
    result = quote(
        db_session,
        drop_pincode="600041",
        order_type="B2B",
        length_cm=D("10"),
        breadth_cm=D("10"),
        height_cm=D("10"),
        actual_weight_kg=D("2"),
        payment_type="COD",
    )
    assert result["zone_type"] == "INTER_ZONE"
    assert result["rate_per_kg"] == D("45.00")
    assert result["base_charge"] == D("120.00")  # 2kg*45=90 below B2B inter minimum 120
    assert result["total_charge"] == D("145.00")


def test_actual_weight_heavier_than_volumetric_wins(pricing_world, db_session):
    result = quote(
        db_session,
        length_cm=D("10"),
        breadth_cm=D("10"),
        height_cm=D("10"),
        actual_weight_kg=D("5"),
        payment_type="PREPAID",
    )
    assert result["volumetric_weight"] == D("0.20")
    assert result["chargeable_weight"] == D("5")


def test_chargeable_rounds_up_to_whole_kg(pricing_world, db_session):
    result = quote(
        db_session,
        length_cm=D("50"),
        breadth_cm=D("40"),
        height_cm=D("31"),
        actual_weight_kg=D("8"),
        payment_type="PREPAID",
    )
    assert result["volumetric_weight"] == D("12.40")
    assert result["chargeable_weight"] == D("13")


def test_missing_rate_card_raises(pricing_world, db_session):
    uncovered = Zone(name="Uncovered", code="UNC-01")
    db_session.add(uncovered)
    db_session.flush()
    db_session.add(Area(name="Area 700001", pincode="700001", zone_id=uncovered.id))
    db_session.commit()

    with pytest.raises(RateCardNotFoundError):
        quote(db_session, drop_pincode="700001")


def test_unmapped_pincode_raises(db_session):
    with pytest.raises(PincodeNotMappedError):
        quote(db_session, pickup_pincode="999999")


def test_missing_cod_rate_raises(pricing_world, db_session):
    db_session.execute(delete(CODRate).where(CODRate.order_type == "B2C"))
    db_session.commit()
    with pytest.raises(CODRateNotFoundError):
        quote(db_session)


def test_cod_rate_is_order_type_specific(pricing_world, db_session):
    b2c = quote(db_session)
    b2b = quote(db_session, order_type="B2B", payment_type="COD")
    assert b2c["cod_surcharge"] == D("30.00")
    assert b2b["cod_surcharge"] == D("25.00")
