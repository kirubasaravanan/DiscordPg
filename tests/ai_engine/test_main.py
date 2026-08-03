import json

from conftest import fail_next_ollama_call, set_fake_chat_response, set_fake_embedding
from fastapi.testclient import TestClient

from main import app

client = TestClient(app)


def test_health():
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


def test_classify_returns_parsed_fields(fake_ollama_url):
    set_fake_chat_response(
        fake_ollama_url,
        json.dumps({"category": "PLUMBING", "priority": "HIGH", "suggested_action": "Send a plumber."}),
    )

    resp = client.post("/classify", json={"description": "The bathroom tap is leaking."})

    assert resp.status_code == 200
    body = resp.json()
    assert body == {"category": "PLUMBING", "priority": "HIGH", "suggested_action": "Send a plumber."}


def test_classify_surfaces_502_when_ollama_returns_invalid_json(fake_ollama_url):
    set_fake_chat_response(fake_ollama_url, "not json at all")

    resp = client.post("/classify", json={"description": "The bathroom tap is leaking."})

    assert resp.status_code == 502


def test_classify_surfaces_502_when_ollama_is_unreachable(fake_ollama_url):
    fail_next_ollama_call(fake_ollama_url)

    resp = client.post("/classify", json={"description": "The bathroom tap is leaking."})

    assert resp.status_code == 502


def test_summarize_returns_trimmed_text(fake_ollama_url):
    set_fake_chat_response(fake_ollama_url, "  Occupancy is stable; two rents are overdue.  ")

    resp = client.post("/summarize", json={"stats": {"occupancy": {"total_beds": 12}}})

    assert resp.status_code == 200
    assert resp.json()["summary"] == "Occupancy is stable; two rents are overdue."


def test_answer_returns_text(fake_ollama_url):
    set_fake_chat_response(fake_ollama_url, "Rent is due on the 5th of each month.")

    resp = client.post(
        "/answer",
        json={
            "question": "When is rent due?",
            "context": [{"source": "pg_rules.md", "content": "Rent is due on the 5th."}],
        },
    )

    assert resp.status_code == 200
    assert resp.json()["answer"] == "Rent is due on the 5th of each month."


def test_embed_returns_vector(fake_ollama_url):
    set_fake_embedding(fake_ollama_url, [0.5, 0.25, 0.1])

    resp = client.post("/embed", json={"text": "hello"})

    assert resp.status_code == 200
    assert resp.json()["embedding"] == [0.5, 0.25, 0.1]


def test_embed_surfaces_502_when_ollama_is_unreachable(fake_ollama_url):
    fail_next_ollama_call(fake_ollama_url)

    resp = client.post("/embed", json={"text": "hello"})

    assert resp.status_code == 502
