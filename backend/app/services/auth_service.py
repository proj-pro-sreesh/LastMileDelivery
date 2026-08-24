from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import hash_password, verify_password
from app.models.user import User, UserRole


class EmailAlreadyRegisteredError(Exception):
    pass


def register_customer(db: Session, *, name: str, email: str, phone: str | None, password: str) -> User:
    normalized_email = email.strip().lower()
    existing = db.scalar(select(User).where(User.email == normalized_email))
    if existing is not None:
        raise EmailAlreadyRegisteredError(normalized_email)
    user = User(
        name=name.strip(),
        email=normalized_email,
        phone=phone,
        password_hash=hash_password(password),
        role=UserRole.CUSTOMER,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def authenticate(db: Session, *, email: str, password: str) -> User | None:
    user = db.scalar(select(User).where(User.email == email.strip().lower()))
    if user is None or not verify_password(password, user.password_hash):
        return None
    return user
