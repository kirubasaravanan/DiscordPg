"""Typed exceptions that main.py's exception handler turns into the
docs/API.md §6 error envelope. Services and dependencies raise these
directly instead of a raw fastapi.HTTPException, so every error response —
regardless of which layer raised it — has the same {"error": {...}} shape.
"""


class APIError(Exception):
    def __init__(self, status_code: int, code: str, message: str, field: str | None = None) -> None:
        self.status_code = status_code
        self.code = code
        self.message = message
        self.field = field
        super().__init__(message)


def not_found(message: str) -> APIError:
    return APIError(404, "NOT_FOUND", message)


def conflict(message: str, field: str | None = None) -> APIError:
    return APIError(409, "CONFLICT", message, field)


def forbidden(message: str = "Not authorized for this resource.") -> APIError:
    return APIError(403, "FORBIDDEN", message)


def unauthorized(message: str = "Missing or invalid credentials.") -> APIError:
    return APIError(401, "UNAUTHORIZED", message)


def bad_request(message: str, field: str | None = None) -> APIError:
    return APIError(400, "VALIDATION_ERROR", message, field)
