"""HTTP client to ai_engine/ — the *only* place in the backend that knows
ai_engine/'s endpoints. Never calls Ollama directly (docs/AI_DESIGN.md §1).

Every function raises AIServiceError on any failure (unreachable, timeout,
non-2xx, malformed response) so callers can degrade gracefully — AI is an
enhancement, not a hard dependency for core flows like filing a complaint.
"""

import httpx

from app.config import get_settings


class AIServiceError(Exception):
    """ai_engine/ was unreachable or returned something unusable."""


def _post(path: str, json: dict) -> dict:
    settings = get_settings()
    try:
        with httpx.Client(base_url=settings.ai_engine_url, timeout=settings.ai_engine_timeout_seconds) as client:
            resp = client.post(path, json=json)
    except httpx.HTTPError as exc:
        raise AIServiceError(f"Could not reach ai_engine at {path}: {exc}") from exc
    if resp.status_code >= 400:
        raise AIServiceError(f"ai_engine {path} failed ({resp.status_code}): {resp.text}")
    try:
        return resp.json()
    except ValueError as exc:
        raise AIServiceError(f"ai_engine {path} returned non-JSON: {resp.text[:500]}") from exc


def classify_complaint(description: str) -> dict:
    """Returns `{"category": str, "priority": str, "suggested_action": str | None}`
    — raw model output, NOT validated against the real enums. Validation is
    the caller's job (app/services/complaint_service.py) — see
    docs/AI_DESIGN.md §2 and docs/ARCHITECTURE.md §5 item 5.
    """
    return _post("/classify", {"description": description})


def generate_summary(stats: dict) -> str:
    return _post("/summarize", {"stats": stats})["summary"]


def answer_question(question: str, context: list[dict]) -> str:
    return _post("/answer", {"question": question, "context": context})["answer"]


def embed_text(text: str) -> list[float]:
    return _post("/embed", {"text": text})["embedding"]
