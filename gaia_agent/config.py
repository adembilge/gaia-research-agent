import os
from dataclasses import asdict, dataclass, field

from dotenv import load_dotenv


class InferenceAccountError(ValueError):
    """A token, permission, or billing problem that requires account action."""


@dataclass(frozen=True)
class Settings:
    token: str = field(repr=False, default="")
    provider: str = "openai"
    model: str = "gpt-4.1"
    vision_model: str = "gpt-4.1"
    asr_model: str = "gpt-transcribe"
    asr_provider: str = "openai"
    base_url: str = "https://api.openai.com/v1"
    max_steps: int = 18
    max_tokens: int = 4096
    timeout: float = 90

    @classmethod
    def from_env(cls):
        load_dotenv()
        provider = os.getenv("INFERENCE_PROVIDER", "openai").strip().lower()
        hf = provider == "huggingface"
        return cls(
            provider=provider,
            token=os.getenv("HF_TOKEN" if hf else "OPENAI_API_KEY", ""),
            model=os.getenv("MODEL_ID", "openai/gpt-oss-120b" if hf else cls.model),
            vision_model=os.getenv(
                "VISION_MODEL_ID", "Qwen/Qwen2.5-VL-72B-Instruct" if hf else cls.vision_model
            ),
            asr_model=os.getenv("ASR_MODEL_ID", "openai/whisper-large-v3" if hf else cls.asr_model),
            asr_provider=os.getenv("HF_ASR_PROVIDER", "hf-inference") if hf else "openai",
            base_url=os.getenv("MODEL_BASE_URL", "https://router.huggingface.co/v1" if hf else cls.base_url),
            max_steps=int(os.getenv("MAX_STEPS", "18")),
            max_tokens=int(os.getenv("MAX_TOKENS", "4096")),
            timeout=float(os.getenv("REQUEST_TIMEOUT", "90")),
        )

    def validate(self):
        if self.provider not in {"openai", "huggingface"}:
            raise ValueError("INFERENCE_PROVIDER must be openai or huggingface.")
        if not self.token:
            key_name = "OPENAI_API_KEY" if self.provider == "openai" else "HF_TOKEN"
            raise ValueError(f"{key_name} is missing. Add it to .env locally or to your Space secrets.")
        expected_url = (
            "https://api.openai.com/v1" if self.provider == "openai" else "https://router.huggingface.co/v1"
        )
        if self.base_url.rstrip("/") != expected_url:
            raise ValueError(
                f"MODEL_BASE_URL must be {expected_url} for {self.provider}; refusing to send credentials to another service."
            )
        if not 1 <= self.max_steps <= 40 or not 256 <= self.max_tokens <= 16384:
            raise ValueError("MAX_STEPS must be 1..40 and MAX_TOKENS must be 256..16384.")
        if not 5 <= self.timeout <= 300:
            raise ValueError("REQUEST_TIMEOUT must be 5..300 seconds.")

    def public(self):
        return {key: value for key, value in asdict(self).items() if key != "token"}


def safe_error(exc: Exception, token: str = "") -> str:
    """Avoid copying request headers, response bodies, or credentials into public logs."""
    import re

    if isinstance(exc, ValueError):
        message = str(exc)
    else:
        status = getattr(exc, "status_code", None) or getattr(
            getattr(exc, "response", None), "status_code", None
        )
        message = type(exc).__name__ + (f" (HTTP {status})" if status else "")
    if token:
        message = message.replace(token, "[redacted]")
    return re.sub(r"(?:hf_[A-Za-z0-9]+|sk-[A-Za-z0-9_-]+)", "[redacted]", message)[:500]
