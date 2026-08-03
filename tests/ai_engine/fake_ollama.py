"""A minimal FastAPI app that mimics just enough of Ollama's REST API
shape (https://github.com/ollama/ollama/blob/main/docs/api.md) to test
ai_engine/'s ollama_client.py for real, over real HTTP — the same role
`moto` plays for AWS in the backend's S3 storage tests (Phase 3c). This is
NOT a substitute for verifying actual model output quality; it only
proves ai_engine/ builds correct requests and parses responses correctly.
See docs/AI_DESIGN.md §7.

Responses are controlled by test code via the /_test/* control endpoints
below (a real, second HTTP server, not a monkeypatch) so each test can say
exactly what "the model" should return without coupling to prompt wording.
"""

from fastapi import FastAPI
from fastapi.responses import JSONResponse
from pydantic import BaseModel

app = FastAPI()

_state: dict = {"chat_response": None, "embedding": None, "fail_next": False}


class SetChatResponse(BaseModel):
    content: str


class SetEmbedding(BaseModel):
    embedding: list[float]


@app.post("/_test/set_chat_response")
def set_chat_response(payload: SetChatResponse) -> dict:
    _state["chat_response"] = payload.content
    return {"ok": True}


@app.post("/_test/set_embedding")
def set_embedding(payload: SetEmbedding) -> dict:
    _state["embedding"] = payload.embedding
    return {"ok": True}


@app.post("/_test/fail_next")
def fail_next() -> dict:
    _state["fail_next"] = True
    return {"ok": True}


@app.post("/_test/reset")
def reset() -> dict:
    _state.update({"chat_response": None, "embedding": None, "fail_next": False})
    return {"ok": True}


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.post("/api/chat", response_model=None)
def chat(payload: dict) -> JSONResponse | dict:
    if _state["fail_next"]:
        _state["fail_next"] = False
        return JSONResponse(status_code=500, content={"error": "simulated Ollama failure"})
    content = _state["chat_response"] or (
        '{"category": "OTHER", "priority": "MEDIUM", "suggested_action": "Review manually."}'
    )
    return {"model": payload.get("model"), "message": {"role": "assistant", "content": content}, "done": True}


@app.post("/api/embeddings", response_model=None)
def embeddings(payload: dict) -> JSONResponse | dict:
    del payload
    if _state["fail_next"]:
        _state["fail_next"] = False
        return JSONResponse(status_code=500, content={"error": "simulated Ollama failure"})
    vector = _state["embedding"] or [0.1] * 768
    return {"embedding": vector}
