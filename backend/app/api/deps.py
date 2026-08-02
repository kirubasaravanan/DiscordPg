import uuid
from dataclasses import dataclass

from fastapi import Depends, Query
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.api.errors import forbidden, unauthorized
from app.database.connection import get_db
from app.models import Tenant, User, UserRole
from app.security.jwt import TokenError, TokenType, decode_token

bearer_scheme = HTTPBearer(auto_error=False)


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> User:
    if credentials is None:
        raise unauthorized("Missing bearer token.")
    try:
        payload = decode_token(credentials.credentials)
    except TokenError:
        raise unauthorized("Invalid or expired token.")
    if payload.get("type") != TokenType.ACCESS.value:
        raise unauthorized("Not an access token.")
    try:
        user_id = uuid.UUID(payload["sub"])
    except (KeyError, ValueError):
        raise unauthorized("Malformed token.")
    user = db.get(User, user_id)
    if user is None or not user.is_active or user.is_deleted:
        raise unauthorized("User not found or inactive.")
    return user


def require_roles(*roles: UserRole):
    """RBAC dependency factory — the single place role checks happen, per
    docs/ARCHITECTURE.md §7 ("enforced as a dependency, not ad hoc per-handler
    checks"). Usage: `Depends(require_roles(UserRole.OWNER, UserRole.MANAGER))`.
    """

    def checker(current_user: User = Depends(get_current_user)) -> User:
        if current_user.role not in roles:
            allowed = ", ".join(r.value for r in roles)
            raise forbidden(f"Requires one of roles: {allowed}.")
        return current_user

    return checker


def get_current_tenant(
    current_user: User = Depends(require_roles(UserRole.TENANT)),
    db: Session = Depends(get_db),
) -> Tenant:
    """Resolves the Tenant row linked to the authenticated TENANT user.

    This is what makes tenant self-service endpoints scope to "your own
    data" rather than a client-supplied id, per docs/ARCHITECTURE.md §7.
    """
    tenant = db.query(Tenant).filter(Tenant.user_id == current_user.id).first()
    if tenant is None:
        raise forbidden("This account has no linked tenant profile.")
    return tenant


@dataclass
class PageParams:
    page: int
    page_size: int

    @property
    def offset(self) -> int:
        return (self.page - 1) * self.page_size


def page_params(page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100)) -> PageParams:
    return PageParams(page=page, page_size=page_size)
