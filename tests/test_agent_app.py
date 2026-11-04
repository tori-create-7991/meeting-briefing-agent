"""The Agent Runtime entry point must not keep meeting text around."""

import importlib
from pathlib import Path

from google.adk.sessions import InMemorySessionService

AGENT_RUNTIME_TF = Path(__file__).resolve().parents[1] / "infra" / "main" / "agent_runtime.tf"


def load_agent_app(monkeypatch, **env):
    # AdkApp looks up a project when it is built; Agent Runtime sets these.
    monkeypatch.setenv("GOOGLE_CLOUD_PROJECT", "test-project")
    monkeypatch.setenv("GOOGLE_CLOUD_LOCATION", "us-central1")
    for name, value in env.items():
        monkeypatch.setenv(name, value)
    from meeting_briefing_agent import agent_app

    return importlib.reload(agent_app)


def test_tracing_is_not_turned_on_through_the_old_flag(monkeypatch):
    agent_app = load_agent_app(monkeypatch)

    # AdkApp.set_up() sets ADK_CAPTURE_MESSAGE_CONTENT_IN_SPANS=true whenever
    # enable_tracing is True, which puts the full LLM request and response
    # (event and document text) on the spans. Left unset, it sets false.
    assert agent_app.app._tmpl_attrs.get("enable_tracing") is None


def test_tracing_is_on_with_the_telemetry_env_var(monkeypatch):
    agent_app = load_agent_app(monkeypatch, GOOGLE_CLOUD_AGENT_ENGINE_ENABLE_TELEMETRY="true")

    assert agent_app.app._tracing_enabled() is True


def test_deployed_agent_sets_the_telemetry_env_var():
    text = AGENT_RUNTIME_TF.read_text()

    assert 'name  = "GOOGLE_CLOUD_AGENT_ENGINE_ENABLE_TELEMETRY"' in text
    after = text.split('name  = "GOOGLE_CLOUD_AGENT_ENGINE_ENABLE_TELEMETRY"', 1)[1]
    assert after.lstrip().startswith('value = "true"')
    assert "ADK_CAPTURE_MESSAGE_CONTENT_IN_SPANS" not in text


def test_sessions_stay_in_memory(monkeypatch):
    agent_app = load_agent_app(monkeypatch)

    assert isinstance(agent_app.build_session_service(), InMemorySessionService)
    # Without a builder, AdkApp on Agent Runtime stores every session (with
    # the event and document text in its state) in the managed session store.
    assert agent_app.app._tmpl_attrs["session_service_builder"] is agent_app.build_session_service
