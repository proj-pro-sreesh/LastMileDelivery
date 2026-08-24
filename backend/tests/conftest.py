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

settings = get_settings()


def _ensure_test_database() -> None:
    """Create the test database if it does not exist yet."""
    conninfo = "postgresql://" + settings.test_database_url.split("://", 1)[1]
    admin_conninfo = re.sub(r"/[^/?]*(\?.*)?$", "/postgres", conninfo)
    target = conninfo.split("?", 1)[0].rsplit("/", 1)[-1]
    try:
        with psycopg.connect(admin_conninfo) as conn:
            conn.autocommit = True
            conn.execute(f'CREATE DATABASE "{target}"')
    except psycopg.errors.DuplicateDatabase:
        pass


@pytest.fixture(scope="session")
def test_engine():
    _ensure_test_database()
    engine = create_engine(settings.test_database_url)
    Base.metadata.create_all(engine)
    yield engine
    engine.dispose()


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
