"""Seed demo/reference data: zones, areas, rate cards, COD rates, admin & agent users.

Idempotent: safe to run repeatedly. Run from backend/:
    ../.venv/bin/python scripts/seed.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.core.security import hash_password
from app.models import Area, CODRate, RateCard, User, UserRole, Zone
from app.models.enums import OrderType

ZONES = [
    ("Chennai Central", "CHE-CEN", ["600001", "600002"]),
    ("Chennai South", "CHE-STH", ["600041", "600042"]),
    ("Bengaluru East", "BLR-EST", ["560001", "560038"]),
]

# rate_per_kg, minimum_charge keyed by (order_type, intra?)
RATE_MATRIX = {
    ("B2B", True): ("30.00", "80.00"),
    ("B2B", False): ("45.00", "120.00"),
    ("B2C", True): ("40.00", "100.00"),
    ("B2C", False): ("60.00", "150.00"),
}

COD_SURCHARGES = {OrderType.B2B: "25.00", OrderType.B2C: "30.00"}

USERS = [
    ("Admin User", "admin@lastmile-demo.com", "9999000001", "Admin@123", UserRole.ADMIN),
    ("Vijay Agent", "agent.vijay@lastmile-demo.com", "9999000002", "Agent@123", UserRole.AGENT),
    ("Priya Agent", "agent.priya@lastmile-demo.com", "9999000003", "Agent@123", UserRole.AGENT),
]


def seed(session: Session) -> None:
    zones_by_code: dict[str, Zone] = {}
    for name, code, pincodes in ZONES:
        zone = session.scalar(select(Zone).where(Zone.code == code))
        if zone is None:
            zone = Zone(name=name, code=code)
            session.add(zone)
            session.flush()
        zones_by_code[code] = zone
        for pin in pincodes:
            if session.scalar(select(Area).where(Area.pincode == pin)) is None:
                session.add(Area(name=f"{name} Area {pin}", pincode=pin, zone_id=zone.id))

    for (order_type_str, is_intra), (rate, minimum) in RATE_MATRIX.items():
        for from_zone in zones_by_code.values():
            targets = [from_zone] if is_intra else [z for z in zones_by_code.values() if z.id != from_zone.id]
            for to_zone in targets:
                exists = session.scalar(
                    select(RateCard).where(
                        RateCard.order_type == order_type_str,
                        RateCard.from_zone_id == from_zone.id,
                        RateCard.to_zone_id == to_zone.id,
                    )
                )
                if exists is None:
                    session.add(
                        RateCard(
                            order_type=order_type_str,
                            from_zone_id=from_zone.id,
                            to_zone_id=to_zone.id,
                            rate_per_kg=rate,
                            minimum_charge=minimum,
                        )
                    )

    for order_type, surcharge in COD_SURCHARGES.items():
        if session.scalar(select(CODRate).where(CODRate.order_type == order_type.value)) is None:
            session.add(CODRate(order_type=order_type.value, surcharge=surcharge))

    for name, email, phone, password, role in USERS:
        if session.scalar(select(User).where(User.email == email)) is None:
            session.add(User(name=name, email=email, phone=phone, password_hash=hash_password(password), role=role))

    session.commit()


def main() -> None:
    with SessionLocal() as session:
        seed(session)
    print("Seed complete.")
    print("  Zones:", ", ".join(code for _, code, _ in ZONES))
    print("  Admin login:     admin@lastmile-demo.com / Admin@123")
    print("  Agent logins:    agent.vijay@lastmile-demo.com, agent.priya@lastmile-demo.com / Agent@123")


if __name__ == "__main__":
    main()
