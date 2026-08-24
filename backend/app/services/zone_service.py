from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import Area, Zone


class PincodeNotMappedError(Exception):
    def __init__(self, pincode: str):
        self.pincode = pincode
        super().__init__(f"Pincode {pincode} is not mapped to any configured area/zone")


class DuplicateError(Exception):
    pass


class NotFoundError(Exception):
    pass


def get_zone_for_pincode(db: Session, pincode: str) -> Zone:
    area = db.scalar(select(Area).where(Area.pincode == pincode.strip()))
    if area is None:
        raise PincodeNotMappedError(pincode)
    return db.get(Zone, area.zone_id)


def list_zones(db: Session) -> list[Zone]:
    return list(db.scalars(select(Zone).order_by(Zone.name)))


def create_zone(db: Session, *, name: str, code: str) -> Zone:
    zone = Zone(name=name.strip(), code=code.strip().upper())
    db.add(zone)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise DuplicateError(f"Zone code '{code}' already exists") from exc
    db.refresh(zone)
    return zone


def update_zone(db: Session, zone_id, *, name: str | None = None, code: str | None = None) -> Zone:
    zone = db.get(Zone, zone_id)
    if zone is None:
        raise NotFoundError("Zone not found")
    if name is not None:
        zone.name = name.strip()
    if code is not None:
        zone.code = code.strip().upper()
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise DuplicateError(f"Zone code '{code}' already exists") from exc
    db.refresh(zone)
    return zone


def delete_zone(db: Session, zone_id) -> None:
    zone = db.get(Zone, zone_id)
    if zone is None:
        raise NotFoundError("Zone not found")
    try:
        db.delete(zone)
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise DuplicateError("Zone still has areas or rate cards referencing it") from exc


def get_area(db: Session, area_id) -> Area | None:
    return db.get(Area, area_id)


def list_areas(db: Session, *, zone_id=None) -> list[Area]:
    query = select(Area).order_by(Area.pincode)
    if zone_id is not None:
        query = query.where(Area.zone_id == zone_id)
    return list(db.scalars(query))


def create_area(db: Session, *, name: str, pincode: str, zone_id) -> Area:
    if db.get(Zone, zone_id) is None:
        raise NotFoundError("Zone not found")
    area = Area(name=name.strip(), pincode=pincode.strip(), zone_id=zone_id)
    db.add(area)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise DuplicateError(f"Pincode {pincode} is already mapped to an area") from exc
    db.refresh(area)
    return area


def update_area(db: Session, area_id, *, name: str | None = None, pincode: str | None = None, zone_id=None) -> Area:
    area = db.get(Area, area_id)
    if area is None:
        raise NotFoundError("Area not found")
    if name is not None:
        area.name = name.strip()
    if pincode is not None:
        area.pincode = pincode.strip()
    if zone_id is not None:
        if db.get(Zone, zone_id) is None:
            raise NotFoundError("Zone not found")
        area.zone_id = zone_id
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise DuplicateError("Pincode is already mapped to another area") from exc
    db.refresh(area)
    return area


def delete_area(db: Session, area_id) -> None:
    area = db.get(Area, area_id)
    if area is None:
        raise NotFoundError("Area not found")
    db.delete(area)
    db.commit()
