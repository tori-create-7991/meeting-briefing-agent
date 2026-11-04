"""The Agent Runtime entry point must not keep meeting text around."""

import importlib

from google.adk.sessions import InMemorySessionService


def load_agent_app(monkeypatch, **env):
    monkeypatch.delenv("ADK_CAPTURE_MESSAGE_CONTENT_IN_SPANS", raising=False)
    # AdkApp looks up a project when it is built; Agent Runtime sets these.
    monkeypatch.setenv("GOOGLE_CLOUD_PROJECT", "test-project")
    monkeypatch.setenv("GOOGLE_CLOUD_LOCATION", "us-central1")
    for name, value in env.items():
        monkeypatch.setenv(name, value)
    from meeting_briefing_agent import agent_app

    return importlib.reload(agent_app)


def test_spans_leave_out_llm_request_and_response(monkeypatch):
    load_agent_app(monkeypatch)

    import os

    assert os.environ["ADK_CAPTURE_MESSAGE_CONTENT_IN_SPANS"] == "false"


def test_span_content_setting_can_be_overridden(monkeypatch):
    load_agent_app(monkeypatch, ADK_CAPTURE_MESSAGE_CONTENT_IN_SPANS="true")

    import os

    assert os.environ["ADK_CAPTURE_MESSAGE_CONTENT_IN_SPANS"] == "true"


def test_sessions_stay_in_memory(monkeypatch):
    agent_app = load_agent_app(monkeypatch)

    assert isinstance(agent_app.build_session_service(), InMemorySessionService)
    # Without a builder, AdkApp on Agent Runtime stores every session (with
    # the event and document text in its state) in the managed session store.
    assert agent_app.app._tmpl_attrs["session_service_builder"] is agent_app.build_session_service
