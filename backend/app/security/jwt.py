import datetime
import uuid
from enum import Enum
from typing import Any

import jwt

from app.config import get_settings


class TokenType(str, Enum):
    ACCESS = "access"
    REFRESH = "refresh"


class TokenError(Exception):
    """Raised for any missing, malformed, expired, or wrong-type token.

    Deliberately generic — callers (api/deps.py) are responsible for turning
    this into the HTTP-facing 401, not this module.
    """


def _now() -> datetime.datetime:
    return datetime.datetime.now(datetime.timezone.utc)


def create_access_token(user_id: uuid.UUID, role: str) -> str:
    settings = get_settings()
    now = _now()
    payload = {
        "sub": str(user_id),
        "role": role,
        "type": TokenType.ACCESS.value,
        "iat": now,
        "exp": now + datetime.timedelta(minutes=settings.access_token_expire_minutes),
    }
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def create_refresh_token(user_id: uuid.UUID, token_version: int) -> str:
    """`token_version` is snapshotted from users.token_version at issuance —
    logout bumps the column so every refresh token issued before it stops
    validating (see decode_token callers in api/deps.py / services/auth_service.py).
    """
    settings = get_settings()
    now = _now()
    payload = {
        "sub": str(user_id),
        "ver": token_version,
        "type": TokenType.REFRESH.value,
        "iat": now,
        "exp": now + datetime.timedelta(days=settings.refresh_token_expire_days),
    }
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def decode_token(token: str) -> dict[str, Any]:
    settings = get_settings()
    try:
        return jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])
    except jwt.PyJWTError as exc:
        raise TokenError(str(exc)) from exc
