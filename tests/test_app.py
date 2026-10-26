from types import SimpleNamespace

import gradio as gr
import pytest

from app import authorize, build_app


def test_app_builds_without_credentials(monkeypatch):
    monkeypatch.delenv("SPACE_ID", raising=False)
    assert build_app().config["title"] == "GAIA Research Agent"


def test_public_space_does_not_expose_owner_credits(monkeypatch):
    monkeypatch.setenv("SPACE_ID", "owner/agent")
    monkeypatch.setenv("ALLOWED_HF_USERS", "trusted")
    for profile in (None, SimpleNamespace(username="stranger")):
        with pytest.raises(gr.Error):
            authorize(profile)
    authorize(SimpleNamespace(username="owner"))
    authorize(SimpleNamespace(username="trusted"))
