import uuid
from typing import Any

from sqlalchemy.orm import Session

from app.api.errors import unauthorized
from app.config import get_settings
from app.models import User
from app.security.jwt import TokenError, TokenType, create_access_token, create_refresh_token, decode_token
from app.security.password import verify_password

# Same message regardless of *why* login failed (unknown identifier vs. wrong
# password) — do not let the API confirm whether an identifier is registered.
_INVALID_CREDENTIALS = "Invalid credentials."


def authenticate(db: Session, identifier: str, password: str) -> User:
    user = db.query(User).filter((User.email == identifier) | (User.phone == identifier)).first()
    if user is None or user.is_deleted or not user.is_active:
        raise unauthorized(_INVALID_CREDENTIALS)
    if not verify_password(password, user.password_hash):
        raise unauthorized(_INVALID_CREDENTIALS)
    return user


def issue_tokens(user: User) -> dict[str, Any]:
    settings = get_settings()
    return {
        "access_token": create_access_token(user.id, user.role.value),
        "refresh_token": create_refresh_token(user.id, user.token_version),
        "token_type": "bearer",
        "expires_in": settings.access_token_expire_minutes * 60,
        "role": user.role.value,
    }


def refresh_access_token(db: Session, refresh_token: str) -> dict[str, Any]:
    settings = get_settings()
    try:
        payload = decode_token(refresh_token)
    except TokenError:
        raise unauthorized("Invalid or expired refresh token.")
    if payload.get("type") != TokenType.REFRESH.value:
        raise unauthorized("Not a refresh token.")
    try:
        user_id = uuid.UUID(payload["sub"])
    except (KeyError, ValueError):
        raise unauthorized("Malformed token.")

    user = db.get(User, user_id)
    if user is None or not user.is_active or user.is_deleted:
        raise unauthorized("User not found or inactive.")
    if payload.get("ver") != user.token_version:
        raise unauthorized("Refresh token has been revoked.")

    return {
        "access_token": create_access_token(user.id, user.role.value),
        "token_type": "bearer",
        "expires_in": settings.access_token_expire_minutes * 60,
    }


def logout(db: Session, user: User) -> None:
    """Bumps token_version, which invalidates every refresh token issued
    for this user up to now (see app/security/jwt.py).
    """
    user.token_version += 1
    db.commit()


def link_discord(db: Session, user: User, discord_id: str) -> User:
    """Sets the caller's own discord_id — self-service, any role.

    No manual uniqueness pre-check: `users.discord_id` is already UNIQUE
    (docs/DATABASE.md §4.1), so a collision raises IntegrityError, which
    main.py's handler turns into a 409 — same pattern as create_user/
    update_user in app/services/user_service.py.
    """
    user.discord_id = discord_id
    db.commit()
    db.refresh(user)
    return user
