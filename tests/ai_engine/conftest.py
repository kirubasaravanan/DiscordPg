"""Starts the fake Ollama server (fake_ollama.py) as a real background
HTTP server bound to a real local port, and points ai_engine/'s Settings
at it — ai_engine's own httpx calls go out over real sockets, only the
far end (an actual Ollama + Qwen3) is what's faked. See docs/AI_DESIGN.md §7.
"""

import socket
import threading
import time

import httpx
import pytest
import uvicorn
from fake_ollama import app as fake_ollama_app

import config


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture(scope="session")
def fake_ollama_url():
    port = _free_port()
    server = uvicorn.Server(uvicorn.Config(fake_ollama_app, host="127.0.0.1", port=port, log_level="warning"))
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()

    base_url = f"http://127.0.0.1:{port}"
    for _ in range(50):
        try:
            httpx.get(f"{base_url}/health", timeout=1)
            break
        except httpx.HTTPError:
            time.sleep(0.1)
    else:
        raise RuntimeError("fake Ollama server did not start in time")

    yield base_url

    server.should_exit = True
    thread.join(timeout=5)


@pytest.fixture(autouse=True)
def _point_at_fake_ollama(fake_ollama_url, monkeypatch):
    monkeypatch.setenv("OLLAMA_HOST", fake_ollama_url)
    config.get_settings.cache_clear()
    httpx.post(f"{fake_ollama_url}/_test/reset", timeout=5)
    yield
    config.get_settings.cache_clear()


def set_fake_chat_response(fake_ollama_url: str, content: str) -> None:
    httpx.post(f"{fake_ollama_url}/_test/set_chat_response", json={"content": content}, timeout=5)


def set_fake_embedding(fake_ollama_url: str, embedding: list[float]) -> None:
    httpx.post(f"{fake_ollama_url}/_test/set_embedding", json={"embedding": embedding}, timeout=5)


def fail_next_ollama_call(fake_ollama_url: str) -> None:
    httpx.post(f"{fake_ollama_url}/_test/fail_next", timeout=5)
