from pydantic import BaseModel, Field


class LoginRequest(BaseModel):
    identifier: str = Field(..., min_length=1, description="Email or phone")
    password: str = Field(..., min_length=1)


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int
    role: str


class RefreshRequest(BaseModel):
    refresh_token: str = Field(..., min_length=1)


class AccessTokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int


class DiscordLinkRequest(BaseModel):
    discord_id: str = Field(..., min_length=1, max_length=32)


class DiscordLinkResponse(BaseModel):
    discord_id: str
