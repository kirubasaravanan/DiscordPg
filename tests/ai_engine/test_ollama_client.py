import pytest
from conftest import fail_next_ollama_call, set_fake_chat_response, set_fake_embedding

import ollama_client


async def test_chat_returns_message_content(fake_ollama_url):
    set_fake_chat_response(fake_ollama_url, "hello there")

    result = await ollama_client.chat([{"role": "user", "content": "hi"}])

    assert result == "hello there"


async def test_chat_raises_ollama_error_on_failure(fake_ollama_url):
    fail_next_ollama_call(fake_ollama_url)

    with pytest.raises(ollama_client.OllamaError):
        await ollama_client.chat([{"role": "user", "content": "hi"}])


async def test_chat_raises_ollama_error_when_host_unreachable(monkeypatch):
    monkeypatch.setenv("OLLAMA_HOST", "http://127.0.0.1:1")  # nothing listens here
    import config

    config.get_settings.cache_clear()

    with pytest.raises(ollama_client.OllamaError):
        await ollama_client.chat([{"role": "user", "content": "hi"}])

    config.get_settings.cache_clear()


async def test_embed_returns_vector(fake_ollama_url):
    set_fake_embedding(fake_ollama_url, [1.0, 2.0, 3.0])

    result = await ollama_client.embed("some text")

    assert result == [1.0, 2.0, 3.0]


async def test_embed_raises_ollama_error_on_failure(fake_ollama_url):
    fail_next_ollama_call(fake_ollama_url)

    with pytest.raises(ollama_client.OllamaError):
        await ollama_client.embed("some text")
