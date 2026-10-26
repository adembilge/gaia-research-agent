import pytest

import gaia_agent.config as config
from gaia_agent.config import Settings, safe_error


def test_openai_and_hf_credentials_are_separate(monkeypatch):
    monkeypatch.setattr(config, "load_dotenv", lambda: None)
    monkeypatch.setenv("INFERENCE_PROVIDER", "openai")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-openai")
    monkeypatch.setenv("HF_TOKEN", "hf_test_huggingface")
    settings = Settings.from_env()
    assert settings.token == "sk-test-openai"
    assert "sk-test-openai" not in str(settings.public())
    monkeypatch.setenv("INFERENCE_PROVIDER", "huggingface")
    assert Settings.from_env().token == "hf_test_huggingface"


def test_wrong_provider_endpoint_is_blocked():
    with pytest.raises(ValueError, match="refusing to send credentials"):
        Settings(token="test", base_url="https://router.huggingface.co/v1").validate()


def test_openai_keys_are_redacted():
    assert "sk-proj-example_secret" not in safe_error(ValueError("Failure sk-proj-example_secret"))
