import re
import sys
import uuid
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

import psycopg
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from app.core.config import get_settings
from app.core.database import Base, get_db
from app.main import app
from app.models import UserRole

settings = get_settings()


def _ensure_test_database() -> None:
    """Recreate the test database from scratch so migrations build a pristine schema."""
    conninfo = "postgresql://" + settings.test_database_url.split("://", 1)[1]
    admin_conninfo = re.sub(r"/[^/?]*(\?.*)?$", "/postgres", conninfo)
    target = conninfo.split("?", 1)[0].rsplit("/", 1)[-1]
    with psycopg.connect(admin_conninfo) as conn:
        conn.autocommit = True
        # Kill any lingering connections before dropping.
        conn.execute(
            "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = %s AND pid <> pg_backend_pid()",
            (target,),
        )
        try:
            conn.execute(f'DROP DATABASE "{target}"')
        except psycopg.errors.InvalidCatalogName:
            pass
        conn.execute(f'CREATE DATABASE "{target}"')


@pytest.fixture(scope="session")
def test_engine():
    _ensure_test_database()
    _run_migrations()
    engine = create_engine(settings.test_database_url)
    yield engine
    engine.dispose()


def _run_migrations() -> None:
    """Build the test schema via Alembic so triggers/constraints match production."""
    from alembic import command
    from alembic.config import Config

    cfg = Config()
    cfg.set_main_option("script_location", str(BACKEND_DIR / "alembic"))
    cfg.set_main_option("sqlalchemy.url", settings.test_database_url)
    command.upgrade(cfg, "head")


@pytest.fixture(autouse=True)
def _clean_tables(test_engine):
    yield
    table_names = ", ".join(f'"{name}"' for name in Base.metadata.tables)
    with test_engine.begin() as conn:
        conn.execute(text(f"TRUNCATE TABLE {table_names} CASCADE"))


@pytest.fixture
def db_session(test_engine):
    session = sessionmaker(bind=test_engine, autoflush=False, expire_on_commit=False)()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def client(test_engine):
    testing_session_local = sessionmaker(bind=test_engine, autoflush=False, expire_on_commit=False)

    def override_get_db():
        db = testing_session_local()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    yield TestClient(app)
    app.dependency_overrides.clear()


@pytest.fixture
def make_auth_headers(db_session):
    """Factory: make_auth_headers(role, email=...) -> Authorization headers for that user."""

    from app.core.security import create_access_token, hash_password
    from app.models import User

    created = []

    def _make(role, email=None, name="Test User"):
        email = email or f"{role.value.lower()}.{uuid.uuid4().hex[:8]}@test.local"
        user = User(name=name, email=email, password_hash=hash_password("password123"), role=role)
        db_session.add(user)
        db_session.commit()
        db_session.refresh(user)
        created.append(user)
        return {"Authorization": f"Bearer {create_access_token(user_id=str(user.id), role=user.role.value)}"}

    return _make


@pytest.fixture
def pricing_world(db_session):
    """CHE-CEN (600001,600002), CHE-STH (600041), BLR-EST (560001) with seeded-equivalent rates."""
    from decimal import Decimal

    from app.models import Area, CODRate, RateCard, Zone

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


@pytest.fixture
def customer_headers(make_auth_headers):
    return make_auth_headers(UserRole.CUSTOMER, name="Customer")


@pytest.fixture
def admin_headers(make_auth_headers):
    return make_auth_headers(UserRole.ADMIN, name="Admin")
