from typing import Generic, TypeVar

from pydantic import BaseModel

T = TypeVar("T")


class ErrorDetail(BaseModel):
    code: str
    message: str
    field: str | None = None


class ErrorResponse(BaseModel):
    """Matches docs/API.md §6 — the shape every error response returns,
    in place of FastAPI's default {"detail": ...}.
    """

    error: ErrorDetail


class Page(BaseModel, Generic[T]):
    """Matches docs/API.md §1 pagination envelope."""

    items: list[T]
    page: int
    page_size: int
    total: int
