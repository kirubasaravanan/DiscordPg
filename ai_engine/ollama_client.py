"""Thin async wrapper over Ollama's documented REST API
(https://github.com/ollama/ollama/blob/main/docs/api.md). This is the
*only* module that knows Ollama's request/response shapes — everything
else in ai_engine/ works with plain Python values (messages, text,
vectors).

Not verified against a live Ollama server in this environment — see
docs/AI_DESIGN.md §7. Tested for real against a hand-rolled Ollama-API-
shaped test server (tests/ai_engine/fake_ollama.py) that proves this
module builds requests and parses responses correctly; that is not the
same as proving Qwen3 8B produces good output.
"""

import httpx

from config import get_settings


class OllamaError(Exception):
    """Ollama was unreachable, timed out, or returned something unusable."""


async def chat(messages: list[dict], *, json_mode: bool = False) -> str:
    settings = get_settings()
    payload: dict = {"model": settings.ollama_chat_model, "messages": messages, "stream": False}
    if json_mode:
        payload["format"] = "json"

    try:
        async with httpx.AsyncClient(base_url=settings.ollama_host, timeout=settings.ollama_timeout_seconds) as client:
            resp = await client.post("/api/chat", json=payload)
    except httpx.HTTPError as exc:
        raise OllamaError(f"Could not reach Ollama at {settings.ollama_host}: {exc}") from exc

    if resp.status_code >= 400:
        raise OllamaError(f"Ollama chat call failed ({resp.status_code}): {resp.text}")
    try:
        return resp.json()["message"]["content"]
    except (KeyError, ValueError) as exc:
        raise OllamaError(f"Unexpected Ollama response shape: {resp.text[:500]}") from exc


async def embed(text: str) -> list[float]:
    settings = get_settings()
    payload = {"model": settings.ollama_embed_model, "prompt": text}

    try:
        async with httpx.AsyncClient(base_url=settings.ollama_host, timeout=settings.ollama_timeout_seconds) as client:
            resp = await client.post("/api/embeddings", json=payload)
    except httpx.HTTPError as exc:
        raise OllamaError(f"Could not reach Ollama at {settings.ollama_host}: {exc}") from exc

    if resp.status_code >= 400:
        raise OllamaError(f"Ollama embeddings call failed ({resp.status_code}): {resp.text}")
    try:
        return resp.json()["embedding"]
    except (KeyError, ValueError) as exc:
        raise OllamaError(f"Unexpected Ollama response shape: {resp.text[:500]}") from exc
