from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.users import User
from app.security import hash_password, verify_password


def register_user(db: Session, email: str, password: str) -> User:
    normalized_email = email.strip().lower()

    existing_user = (
        db.query(User)
        .filter(func.lower(User.email) == normalized_email)
        .first()
    )
    if existing_user is not None:
        raise ValueError("Email is already registered")

    user = User(
        email=normalized_email,
        hashed_password=hash_password(password),
    )
    db.add(user)

    try:
        db.commit()
        db.refresh(user)
    except IntegrityError as error:
        db.rollback()
        raise ValueError("Email is already registered") from error

    return user


def authenticate_user(
    db: Session,
    email: str,
    password: str,
) -> User | None:
    normalized_email = email.strip().lower()

    user = (
        db.query(User)
        .filter(func.lower(User.email) == normalized_email)
        .first()
    )

    if user is None or not user.is_active:
        return None

    if not verify_password(password, user.hashed_password):
        return None

    return user