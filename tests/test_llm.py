import json

import httpx
import pytest

from app.extraction import GroqClient, LLMError


def _response(status: int, body: dict) -> httpx.Response:
    request = httpx.Request("POST", GroqClient.url)
    return httpx.Response(status, json=body, request=request)


def _chat(content: str) -> dict:
    return {"choices": [{"message": {"content": content}}]}


def test_returns_parsed_json(monkeypatch):
    sent = {}

    def fake_post(url, json, headers, timeout):
        sent.update(json)
        return _response(200, _chat('{"fields": {}}'))

    monkeypatch.setattr(httpx, "post", fake_post)
    result = GroqClient("key", "some-model").complete_json("system", "user")

    assert result == {"fields": {}}
    assert sent["model"] == "some-model"
    assert sent["temperature"] == 0
    assert sent["response_format"] == {"type": "json_object"}


def test_invalid_json_raises(monkeypatch):
    monkeypatch.setattr(httpx, "post", lambda *a, **k: _response(200, _chat("not json")))
    with pytest.raises(LLMError):
        GroqClient("key", "m").complete_json("s", "u")


def test_non_object_raises(monkeypatch):
    monkeypatch.setattr(httpx, "post", lambda *a, **k: _response(200, _chat(json.dumps([1]))))
    with pytest.raises(LLMError):
        GroqClient("key", "m").complete_json("s", "u")


def test_http_error_raises(monkeypatch):
    monkeypatch.setattr(httpx, "post", lambda *a, **k: _response(401, {"error": "bad key"}))
    with pytest.raises(LLMError):
        GroqClient("key", "m").complete_json("s", "u")


def test_retries_rate_limit_then_succeeds(monkeypatch):
    responses = [
        _response(429, {"error": "rate limited"}),
        _response(200, _chat('{"fields": {}}')),
    ]
    sleeps = []
    monkeypatch.setattr(httpx, "post", lambda *a, **k: responses.pop(0))
    monkeypatch.setattr("app.extraction.llm.time.sleep", sleeps.append)

    assert GroqClient("key", "m").complete_json("s", "u") == {"fields": {}}
    assert sleeps == [2.0]


def test_honours_retry_after(monkeypatch):
    limited = httpx.Response(
        429, headers={"retry-after": "3"}, request=httpx.Request("POST", GroqClient.url)
    )
    responses = [limited, _response(200, _chat("{}"))]
    sleeps = []
    monkeypatch.setattr(httpx, "post", lambda *a, **k: responses.pop(0))
    monkeypatch.setattr("app.extraction.llm.time.sleep", sleeps.append)

    GroqClient("key", "m").complete_json("s", "u")
    assert sleeps == [3.0]


def test_gives_up_after_max_attempts(monkeypatch):
    calls = []

    def always_limited(*a, **k):
        calls.append(1)
        return _response(429, {"error": "rate limited"})

    monkeypatch.setattr(httpx, "post", always_limited)
    monkeypatch.setattr("app.extraction.llm.time.sleep", lambda s: None)
    with pytest.raises(LLMError):
        GroqClient("key", "m", max_attempts=3).complete_json("s", "u")
    assert len(calls) == 3


def test_does_not_retry_client_errors(monkeypatch):
    calls = []

    def unauthorized(*a, **k):
        calls.append(1)
        return _response(401, {"error": "bad key"})

    monkeypatch.setattr(httpx, "post", unauthorized)
    with pytest.raises(LLMError):
        GroqClient("key", "m").complete_json("s", "u")
    assert len(calls) == 1


def test_error_keeps_the_provider_message(monkeypatch):
    body = {"error": {"message": "Rate limit reached for tokens per day (TPD)"}}
    monkeypatch.setattr(httpx, "post", lambda *a, **k: _response(400, body))
    with pytest.raises(LLMError, match="tokens per day"):
        GroqClient("key", "m").complete_json("s", "u")
