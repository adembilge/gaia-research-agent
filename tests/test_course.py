from pathlib import Path

import httpx
import pytest

from gaia_agent.course import CourseClient

TASK = "cca530fc-4052-43b2-b130-b30968d8aa44"
QUESTION = {"task_id": TASK, "file_name": TASK + ".png"}


def unavailable(*args, **kwargs):
    response = httpx.Response(404, request=httpx.Request("GET", "https://example.com"))
    response.raise_for_status()


def test_missing_course_attachment_falls_back_to_exact_official_file(monkeypatch, tmp_path):
    import huggingface_hub

    import gaia_agent.course as module

    cached = tmp_path / "cached.png"
    cached.write_bytes(b"image fixture")
    calls = []

    def download(repo_id, filename, **kwargs):
        calls.append((repo_id, filename))
        assert kwargs["repo_type"] == "dataset"
        assert kwargs["token"] == "test"
        return str(cached)

    monkeypatch.setattr(module, "fetch_url", unavailable)
    monkeypatch.setattr(huggingface_hub, "hf_hub_download", download)
    client = CourseClient(token="test")
    target = client.attachment(QUESTION, tmp_path / "attachments")
    assert calls == [("gaia-benchmark/GAIA", f"2023/validation/{TASK}.png")]
    assert target.read_bytes() == b"image fixture"
    assert client.attachment_sources[TASK].startswith("hf://datasets/gaia-benchmark/GAIA/")


def test_missing_dataset_credentials_gives_actionable_error(monkeypatch, tmp_path):
    import gaia_agent.course as module

    monkeypatch.setattr(module, "fetch_url", unavailable)
    monkeypatch.delenv("HF_TOKEN", raising=False)
    monkeypatch.delenv("HF_DATASET_TOKEN", raising=False)
    with pytest.raises(ValueError, match="HF_DATASET_TOKEN"):
        CourseClient().attachment(QUESTION, tmp_path)


def test_attachment_target_stays_in_requested_directory(monkeypatch, tmp_path):
    import gaia_agent.course as module

    monkeypatch.setattr(module, "fetch_url", lambda *a, **kw: (b"image", "image/png", "url"))
    target = CourseClient().attachment({**QUESTION, "file_name": "../../other.png"}, tmp_path)
    assert target == Path(tmp_path) / f"{TASK}.png"
