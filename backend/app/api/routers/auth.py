from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.database.connection import get_db
from app.models import User
from app.schemas.auth import (
    AccessTokenResponse,
    DiscordLinkRequest,
    DiscordLinkResponse,
    LoginRequest,
    RefreshRequest,
    TokenResponse,
)
from app.services import auth_service

router = APIRouter()


@router.post("/login", response_model=TokenResponse)
def login(payload: LoginRequest, db: Session = Depends(get_db)) -> dict:
    user = auth_service.authenticate(db, payload.identifier, payload.password)
    return auth_service.issue_tokens(user)


@router.post("/refresh", response_model=AccessTokenResponse)
def refresh(payload: RefreshRequest, db: Session = Depends(get_db)) -> dict:
    return auth_service.refresh_access_token(db, payload.refresh_token)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> None:
    auth_service.logout(db, current_user)


@router.post("/link-discord", response_model=DiscordLinkResponse)
def link_discord(
    payload: DiscordLinkRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    user = auth_service.link_discord(db, current_user, payload.discord_id)
    return {"discord_id": user.discord_id}
