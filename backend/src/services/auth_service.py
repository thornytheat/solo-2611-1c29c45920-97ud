"""登录 / 当前用户。"""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.constants import error_codes
from src.models.user import User
from src.utils.errors import AppError
from src.utils.security import create_access_token, verify_password


def authenticate(db: Session, email: str, password: str) -> tuple[str, int, User]:
    user = db.scalar(select(User).where(User.email == email.lower().strip()))
    if user is None or not verify_password(password, user.password_hash):
        raise AppError(error_codes.AUTH_INVALID, 401)
    token, expires_in = create_access_token(user.email, user.role)
    return token, expires_in, user


def get_user(db: Session, email: str) -> User:
    user = db.scalar(select(User).where(User.email == email))
    if user is None:
        raise AppError(error_codes.AUTH_INVALID, 401)
    return user
