"""Tests app/services/ai_client.py — the backend's HTTP contract with
ai_engine/ — against a real ai_engine subprocess pointed at a real fake-
Ollama subprocess (both started by conftest.py's session fixtures). This
is the one hop in the AI chain that's fully real end-to-end in this
environment; only Ollama itself is faked. See docs/AI_DESIGN.md §7.
"""

import pytest
from conftest import reset_fake_ollama, set_fake_chat_response, set_fake_embedding

from app.config import Settings
from app.services import ai_client


@pytest.fixture(autouse=True)
def _reset(fake_ollama_url):
    reset_fake_ollama(fake_ollama_url)


def test_classify_complaint_returns_parsed_fields(configured_ai_client, fake_ollama_url):
    set_fake_chat_response(
        fake_ollama_url,
        '{"category": "PLUMBING", "priority": "HIGH", "suggested_action": "Send a plumber."}',
    )

    result = ai_client.classify_complaint("The tap is leaking.")

    assert result == {"category": "PLUMBING", "priority": "HIGH", "suggested_action": "Send a plumber."}


def test_generate_summary_returns_text(configured_ai_client, fake_ollama_url):
    set_fake_chat_response(fake_ollama_url, "All is well.")

    result = ai_client.generate_summary({"occupancy": {"total_beds": 12}})

    assert result == "All is well."


def test_answer_question_returns_text(configured_ai_client, fake_ollama_url):
    set_fake_chat_response(fake_ollama_url, "Rent is due on the 5th.")

    result = ai_client.answer_question("When is rent due?", [{"source": "rent_policy.md", "content": "..."}])

    assert result == "Rent is due on the 5th."


def test_embed_text_returns_vector(configured_ai_client, fake_ollama_url):
    set_fake_embedding(fake_ollama_url, [0.1, 0.2, 0.3])

    result = ai_client.embed_text("hello")

    assert result == [0.1, 0.2, 0.3]


def test_classify_complaint_raises_ai_service_error_when_ai_engine_unreachable(monkeypatch):
    from app.services import ai_client as ai_client_module

    unreachable = Settings(ai_engine_url="http://127.0.0.1:1")  # nothing listens here
    monkeypatch.setattr(ai_client_module, "get_settings", lambda: unreachable)

    with pytest.raises(ai_client.AIServiceError):
        ai_client.classify_complaint("test")


def test_classify_complaint_raises_ai_service_error_on_ollama_failure(configured_ai_client, fake_ollama_url):
    import httpx

    httpx.post(f"{fake_ollama_url}/_test/fail_next", timeout=5)

    with pytest.raises(ai_client.AIServiceError):
        ai_client.classify_complaint("test")
