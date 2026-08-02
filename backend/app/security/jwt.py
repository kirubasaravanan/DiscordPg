import datetime
import uuid
from enum import Enum
from typing import Any

import jwt

from app.config import get_settings


class TokenType(str, Enum):
    ACCESS = "access"
    REFRESH = "refresh"


class StorageTokenAction(str, Enum):
    """Distinct from TokenType — these scope a token to one storage key and
    one action, not a user identity. Used by the local storage backend's
    internal upload/download routes as a genuine (if homegrown) analog of an
    S3 presigned URL's signature. See app/storage/local.py.
    """

    UPLOAD = "storage_upload"
    DOWNLOAD = "storage_download"


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


def create_storage_token(storage_key: str, action: StorageTokenAction, expire_seconds: int) -> str:
    settings = get_settings()
    now = _now()
    payload = {
        "key": storage_key,
        "action": action.value,
        "iat": now,
        "exp": now + datetime.timedelta(seconds=expire_seconds),
    }
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def decode_storage_token(token: str, expected_action: StorageTokenAction) -> str:
    """Returns the storage_key the token was scoped to. Raises TokenError if
    the token is invalid/expired (via decode_token) or wasn't issued for
    `expected_action` — a download token can't be replayed as an upload one.
    """
    payload = decode_token(token)
    if payload.get("action") != expected_action.value:
        raise TokenError(f"Token is not valid for {expected_action.value}.")
    key = payload.get("key")
    if not key:
        raise TokenError("Token is missing its storage key.")
    return key
