import uuid
from datetime import UTC, datetime, timedelta

import jwt as pyjwt
import pytest
from fastapi import HTTPException
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from app.core.deps import require_role
from app.core.security import ALGORITHM
from app.core.config import get_settings
from app.models.user import User, UserRole

settings = get_settings()

REGISTER_PAYLOAD = {
    "name": "Ada Customer",
    "email": "ada@example.com",
    "phone": "9876543210",
    "password": "supersecret1",
}


def register(client, **overrides):
    return client.post("/auth/register", json={**REGISTER_PAYLOAD, **overrides})


def login(client, email="ada@example.com", password="supersecret1"):
    return client.post("/auth/login", json={"email": email, "password": password})


def auth_headers(token):
    return {"Authorization": f"Bearer {token}"}


def test_register_creates_customer(client):
    response = register(client)
    assert response.status_code == 201
    body = response.json()
    assert body["email"] == "ada@example.com"
    assert body["role"] == "CUSTOMER"
    assert "password" not in body and "password_hash" not in body


def test_register_duplicate_email_case_insensitive(client):
    assert register(client).status_code == 201
    duplicate = register(client, name="Someone Else", email="ADA@EXAMPLE.COM")
    assert duplicate.status_code == 409


@pytest.mark.parametrize(
    "bad_email,bad_password",
    [
        ("not-an-email", "supersecret1"),
        ("ada@example.com", "short"),
    ],
)
def test_register_validation_errors(client, bad_email, bad_password):
    response = register(client, email=bad_email, password=bad_password)
    assert response.status_code == 422


def test_login_success_and_me_roundtrip(client):
    register(client)
    login_response = login(client)
    assert login_response.status_code == 200
    token = login_response.json()["access_token"]

    me_response = client.get("/auth/me", headers=auth_headers(token))
    assert me_response.status_code == 200
    body = me_response.json()
    assert body["email"] == "ada@example.com"
    assert "password_hash" not in body


def test_login_rejects_bad_credentials_without_user_enumeration(client):
    register(client)
    wrong_password = login(client, password="totallywrong")
    unknown_email = login(client, email="ghost@example.com", password="totallywrong")
    assert wrong_password.status_code == unknown_email.status_code == 401
    assert wrong_password.json() == unknown_email.json()


def test_me_requires_token(client):
    assert client.get("/auth/me").status_code == 401


def test_me_rejects_garbage_token(client):
    response = client.get("/auth/me", headers=auth_headers("not-a-real-token"))
    assert response.status_code == 401


def test_me_rejects_expired_token(client):
    expired = pyjwt.encode(
        {"sub": str(uuid.uuid4()), "role": "CUSTOMER", "exp": datetime.now(UTC) - timedelta(hours=1)},
        settings.secret_key,
        algorithm=ALGORITHM,
    )
    response = client.get("/auth/me", headers=auth_headers(expired))
    assert response.status_code == 401


def test_require_role_blocks_other_roles():
    checker = require_role(UserRole.ADMIN)
    agent = User(name="Agent", email="agent@example.com", password_hash="x", role=UserRole.AGENT)
    with pytest.raises(HTTPException) as exc_info:
        checker(agent)
    assert exc_info.value.status_code == 403


def test_require_role_allows_allowed_roles():
    checker = require_role(UserRole.ADMIN, UserRole.CUSTOMER)
    customer = User(name="Cust", email="c@example.com", password_hash="x", role=UserRole.CUSTOMER)
    assert checker(customer) is customer


def test_database_rejects_invalid_role(db_session):
    with pytest.raises(IntegrityError):
        db_session.execute(
            text(
                "INSERT INTO users (id, name, email, password_hash, role) "
                "VALUES (gen_random_uuid(), 'Evil', 'evil@example.com', 'x', 'SUPERUSER')"
            )
        )
