import asyncio
import base64
import json

import pytest
from mcp.server.mcpserver.exceptions import ToolError

from meeting_briefing_mcp import server


class FakeEngine:
    def __init__(self, events):
        self.events = events
        self.calls = []

    async def async_stream_query(self, user_id, message):
        self.calls.append((user_id, json.loads(message)))
        for event in self.events:
            yield event


def writer_event(text):
    return {"author": "briefing_writer", "content": {"parts": [{"text": text}]}}


@pytest.fixture
def engine(monkeypatch):
    fake = FakeEngine([{"author": "context_fetcher", "actions": {}}, writer_event("前半"), writer_event("後半")])
    monkeypatch.setattr(server, "get_engine", lambda: fake)
    return fake


def id_token(payload):
    body = base64.urlsafe_b64encode(json.dumps(payload).encode()).decode().rstrip("=")
    return f"Bearer header.{body}.signature"


class FakeCtx:
    def __init__(self, headers):
        self.headers = headers


def test_get_briefing_queries_agent_and_joins_writer_text(engine):
    ctx = FakeCtx({"authorization": id_token({"email": "me@example.org"})})

    text = asyncio.run(server.get_briefing(date="2026-10-29", max_events=3, ctx=ctx))

    assert text == "前半後半"
    assert engine.calls == [("me@example.org", {"date": "2026-10-29", "max_events": 3})]


def test_get_briefing_defaults(engine):
    asyncio.run(server.get_briefing())

    assert engine.calls == [("anonymous", {"date": None, "max_events": 5})]


@pytest.mark.parametrize("date", ["10/29", "2026-13-01", ""])
def test_get_briefing_rejects_bad_date_without_calling_agent(engine, date):
    with pytest.raises(ToolError, match="YYYY-MM-DD"):
        asyncio.run(server.get_briefing(date=date))
    assert engine.calls == []


@pytest.mark.parametrize("max_events", [0, 21, True])
def test_get_briefing_rejects_out_of_range_max_events(engine, max_events):
    with pytest.raises(ToolError, match="max_events"):
        asyncio.run(server.get_briefing(max_events=max_events))
    assert engine.calls == []


def test_query_agent_raises_on_error_event(monkeypatch):
    fake = FakeEngine([{"error_code": "500", "error_message": "boom"}])
    monkeypatch.setattr(server, "get_engine", lambda: fake)

    with pytest.raises(RuntimeError, match="boom"):
        asyncio.run(server.query_agent({"date": None, "max_events": 5}, "u"))


def test_query_agent_raises_when_no_text(monkeypatch):
    monkeypatch.setattr(server, "get_engine", lambda: FakeEngine([]))

    with pytest.raises(RuntimeError, match="no briefing text"):
        asyncio.run(server.query_agent({"date": None, "max_events": 5}, "u"))


@pytest.mark.parametrize(
    "headers",
    [None, {}, {"authorization": "Bearer opaque-token"}, {"authorization": "Bearer a.!!!.c"}],
)
def test_caller_email_falls_back_to_anonymous(headers):
    assert server.caller_email(headers) == "anonymous"


def test_tool_is_registered_with_documented_parameters():
    tools = asyncio.run(server.mcp.list_tools())
    tool = next(t for t in tools if t.name == "get_briefing")

    assert set(tool.input_schema["properties"]) == {"date", "max_events"}


def call_over_http(arguments):
    from starlette.testclient import TestClient

    headers = {
        "host": "mcp-front-abc-uc.a.run.app",
        "accept": "application/json, text/event-stream",
        "content-type": "application/json",
        "authorization": id_token({"email": "me@example.org"}),
    }
    call = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "tools/call",
        "params": {"name": "get_briefing", "arguments": arguments},
    }
    with TestClient(server.create_app(), base_url="https://mcp-front-abc-uc.a.run.app") as client:
        response = client.post("/mcp", headers=headers, json=call)
    assert response.status_code == 200, response.text
    return response.json()["result"]


def test_http_app_serves_tool_calls_for_a_cloud_run_host(engine):
    result = call_over_http({"date": "2026-10-29"})

    assert result.get("isError") in (None, False)
    assert result["content"][0]["text"] == "前半後半"
    assert engine.calls == [("me@example.org", {"date": "2026-10-29", "max_events": 5})]


def test_http_app_returns_tool_error_for_bad_input(engine):
    result = call_over_http({"date": "10/29"})

    assert result["isError"] is True
    assert "YYYY-MM-DD" in result["content"][0]["text"]
    assert engine.calls == []


def test_get_briefing_reports_agent_failures_with_their_cause(monkeypatch):
    def broken_engine():
        raise PermissionError("403 aiplatform.reasoningEngines.query denied")

    monkeypatch.setattr(server, "get_engine", broken_engine)

    with pytest.raises(ToolError, match="reasoningEngines.query denied"):
        asyncio.run(server.get_briefing())
