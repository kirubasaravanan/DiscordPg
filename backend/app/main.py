from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.exc import IntegrityError
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.api.errors import APIError
from app.api.routers import allocations, auth, beds, buildings, rent_ledger, rooms, tenant_self, tenants

app = FastAPI(title="PG OS API", version="0.1.0")

app.include_router(auth.router, prefix="/api/v1/auth", tags=["auth"])
app.include_router(buildings.router, prefix="/api/v1/buildings", tags=["buildings"])
app.include_router(rooms.router, prefix="/api/v1/rooms", tags=["rooms"])
app.include_router(beds.router, prefix="/api/v1/beds", tags=["beds"])
app.include_router(tenants.router, prefix="/api/v1/tenants", tags=["tenants"])
app.include_router(allocations.router, prefix="/api/v1/allocations", tags=["allocations"])
app.include_router(rent_ledger.router, prefix="/api/v1/rent", tags=["rent"])
app.include_router(tenant_self.router, prefix="/api/v1/tenant", tags=["tenant-self-service"])


@app.exception_handler(APIError)
async def api_error_handler(request: Request, exc: APIError) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": {"code": exc.code, "message": exc.message, "field": exc.field}},
    )


@app.exception_handler(RequestValidationError)
async def validation_error_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    """Reshapes FastAPI/Pydantic's default validation error body into the
    docs/API.md §6 envelope.
    """
    first = exc.errors()[0]
    loc = [str(p) for p in first["loc"] if p not in ("body", "query", "path", "header")]
    field = ".".join(loc) or None
    return JSONResponse(
        status_code=422,
        content={"error": {"code": "VALIDATION_ERROR", "message": first["msg"], "field": field}},
    )


@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
    """Catches anything not raised as an APIError (e.g. FastAPI's own 404 for
    an undefined route, 405 for a wrong method) so every error response uses
    the same envelope shape, not just the ones this codebase raises directly.
    """
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": {"code": "HTTP_ERROR", "message": str(exc.detail), "field": None}},
    )


@app.exception_handler(IntegrityError)
async def integrity_error_handler(request: Request, exc: IntegrityError) -> JSONResponse:
    """Safety net for database constraint violations (unique/check/FK) that a
    service didn't pre-check explicitly — e.g. a duplicate room_number within
    a building. Per docs/API.md §7, these are 409s, never a bare 500.
    """
    return JSONResponse(
        status_code=409,
        content={
            "error": {
                "code": "CONFLICT",
                "message": "The request conflicts with existing data.",
                "field": None,
            }
        },
    )


@app.get("/health", tags=["health"])
async def health() -> dict[str, str]:
    return {"status": "ok"}
