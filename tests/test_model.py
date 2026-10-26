import httpx
import pytest
from openai import APIStatusError

from gaia_agent.config import InferenceAccountError, Settings
from gaia_agent.model import Model


@pytest.mark.parametrize("status", [401, 402, 403])
def test_account_errors_have_actionable_messages_without_response_bodies(monkeypatch, status):
    model = Model(Settings(token="test-secret"))

    def fail(**kwargs):
        response = httpx.Response(status, request=httpx.Request("POST", "https://example.com"))
        raise APIStatusError("sensitive-response-body", response=response, body={"debug": "test-secret"})

    monkeypatch.setattr(model.client.chat.completions, "create", fail)
    with pytest.raises(InferenceAccountError) as caught:
        model.chat([{"role": "user", "content": "test"}])
    assert str(status) in str(caught.value)
    assert "test-secret" not in str(caught.value)
    assert "sensitive-response-body" not in str(caught.value)


def test_openai_quota_failure_is_terminal(monkeypatch):
    model = Model(Settings(token="test-secret"))

    def fail(**kwargs):
        response = httpx.Response(
            429, request=httpx.Request("POST", "https://api.openai.com/v1/chat/completions")
        )
        raise APIStatusError("quota", response=response, body={"code": "insufficient_quota"})

    monkeypatch.setattr(model.client.chat.completions, "create", fail)
    with pytest.raises(InferenceAccountError, match="OpenAI API quota"):
        model.chat([{"role": "user", "content": "test"}])


def test_openai_audio_uses_openai_client_and_extension(monkeypatch):
    from types import SimpleNamespace

    model = Model(Settings(token="test-secret"))
    captured = {}

    def transcribe(**kwargs):
        captured.update(kwargs)
        return SimpleNamespace(text="example transcript")

    monkeypatch.setattr(model.client.audio.transcriptions, "create", transcribe)
    assert model.transcribe_audio(b"audio fixture", "sample.wav") == "example transcript"
    assert captured == {"model": "gpt-transcribe", "file": ("sample.wav", b"audio fixture")}
    assert model.usage["calls"] == 1


def test_openai_completion_uses_supported_token_parameter(monkeypatch):
    from types import SimpleNamespace

    model = Model(Settings(token="test-secret"))
    captured = {}

    def chat(**kwargs):
        captured.update(kwargs)
        return SimpleNamespace(
            usage=None, choices=[SimpleNamespace(finish_reason="stop", message=SimpleNamespace(content="42"))]
        )

    monkeypatch.setattr(model.client.chat.completions, "create", chat)
    model.chat([{"role": "user", "content": "test"}])
    assert captured["max_completion_tokens"] == 4096
    assert "max_tokens" not in captured
