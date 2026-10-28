import asyncio
import json

import pytest
from google.adk.runners import InMemoryRunner
from google.auth.exceptions import RefreshError, TransportError
from google.genai import types

from meeting_briefing_agent import fetcher
from meeting_briefing_agent.fetcher import STATE_KEY, ContextFetcher, parse_request


def run_fetcher(build, text):
    agent = ContextFetcher(name="context_fetcher", build_contexts=build)
    runner = InMemoryRunner(agent=agent, app_name="test")

    async def go():
        session = await runner.session_service.create_session(app_name="test", user_id="u")
        events = []
        async for event in runner.run_async(
            user_id="u",
            session_id=session.id,
            new_message=types.Content(role="user", parts=[types.Part(text=text)]),
        ):
            events.append(event)
        await runner.close()
        return events

    return asyncio.run(go())


def test_fetcher_passes_request_and_stores_contexts_in_state():
    calls = []

    def build(date, max_events):
        calls.append((date, max_events))
        return [{"event": {"summary": "定例"}, "docs": [], "past_meeting_trends": None}]

    events = run_fetcher(build, json.dumps({"date": "2026-10-29", "max_events": 3}))

    assert calls == [("2026-10-29", 3)]
    stored = events[-1].actions.state_delta[STATE_KEY]
    assert json.loads(stored)[0]["event"]["summary"] == "定例"
    assert "定例" in stored


def test_fetcher_stores_empty_list_when_there_are_no_events():
    events = run_fetcher(lambda date, max_events: [], "{}")

    assert events[-1].actions.state_delta[STATE_KEY] == "[]"


def test_parse_request_falls_back_to_defaults():
    assert parse_request("not json") == {"date": None, "max_events": 5}
    assert parse_request('["x"]') == {"date": None, "max_events": 5}
    assert parse_request('{"max_events": 99}') == {"date": None, "max_events": 20}
    assert parse_request('{"max_events": true}') == {"date": None, "max_events": 5}


def patch_workspace(monkeypatch, error):
    monkeypatch.setattr(fetcher, "get_workspace_credentials", lambda: "creds")
    monkeypatch.setattr(fetcher, "build_calendar_service", lambda creds: "cal")
    monkeypatch.setattr(fetcher, "build_docs_service", lambda creds: "docs")

    def fail(*args, **kwargs):
        raise error

    monkeypatch.setattr(fetcher, "build_event_contexts", fail)


def test_sign_permission_error_explains_the_fix(monkeypatch):
    patch_workspace(monkeypatch, TransportError("Error calling the IAM signBlob API: 403"))

    with pytest.raises(RuntimeError, match="signBlob on that account"):
        fetcher.build_contexts_from_workspace(None, 5)


def test_unauthorized_delegation_explains_the_fix(monkeypatch):
    patch_workspace(monkeypatch, RefreshError("unauthorized_client: Client is unauthorized"))

    with pytest.raises(RuntimeError, match="workspace_reader_client_id"):
        fetcher.build_contexts_from_workspace(None, 5)
