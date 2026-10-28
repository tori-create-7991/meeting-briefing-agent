import asyncio
import json
from types import SimpleNamespace

import pytest

from meeting_briefing_agent import main as main_module
from meeting_briefing_agent.main import run_briefings


def text_event(text):
    part = SimpleNamespace(text=text)
    return SimpleNamespace(
        error_code=None, error_message=None, content=SimpleNamespace(parts=[part])
    )


def error_event(code, message):
    return SimpleNamespace(error_code=code, error_message=message, content=None)


class FakeSessionService:
    async def create_session(self, app_name, user_id):
        return SimpleNamespace(id="session")


class FakeRunner:
    """Replays a scripted reply per call: a list of events, or an exception."""

    def __init__(self, replies):
        self._replies = list(replies)
        self.session_service = FakeSessionService()

    async def run_async(self, user_id, session_id, new_message):
        reply = self._replies.pop(0)
        if isinstance(reply, Exception):
            raise reply
        for event in reply:
            yield event


def run(runner, contexts):
    lines = []
    failures = asyncio.run(run_briefings(runner, contexts, out=lines.append))
    return failures, lines


def context(summary):
    return {"event": {"summary": summary}, "docs": [], "past_meeting_trends": None}


def test_run_briefings_continues_after_one_event_fails():
    runner = FakeRunner([RuntimeError("429 quota"), [text_event("Second briefing")]])

    failures, lines = run(runner, [context("First"), context("Second")])

    assert failures == 1
    assert any("429 quota" in line for line in lines)
    assert "Second briefing" in lines


def test_run_briefings_reports_model_error_event_instead_of_empty_briefing():
    runner = FakeRunner([[error_event("SAFETY", "blocked")]])

    failures, lines = run(runner, [context("Blocked")])

    assert failures == 1
    assert any("SAFETY" in line for line in lines)


def test_run_briefings_strips_terminal_control_characters_from_titles():
    runner = FakeRunner([[text_event("ok")]])

    _, lines = run(runner, [context("Evil\x1b[2Jtitle")])

    assert "\x1b" not in lines[0]


class RecordingRunner(FakeRunner):
    def __init__(self, replies):
        super().__init__(replies)
        self.messages = []

    async def run_async(self, user_id, session_id, new_message):
        self.messages.append(new_message)
        async for event in super().run_async(user_id, session_id, new_message):
            yield event


def test_run_briefings_sends_only_the_context_keys_and_keeps_non_ascii_text():
    runner = RecordingRunner([[text_event("ok")]])

    run(runner, [context("週次定例")])

    payload = runner.messages[0].parts[0].text
    assert set(json.loads(payload)) == {"event", "docs", "past_meeting_trends"}
    assert "週次定例" in payload


@pytest.mark.parametrize("raw", ["0", "51", "abc"])
def test_read_max_events_rejects_out_of_range_values(monkeypatch, raw):
    monkeypatch.setenv("CALENDAR_MAX_EVENTS", raw)

    with pytest.raises(SystemExit):
        main_module._read_max_events()


def test_read_max_events_accepts_valid_value(monkeypatch):
    monkeypatch.setenv("CALENDAR_MAX_EVENTS", "7")

    assert main_module._read_max_events() == 7


@pytest.mark.parametrize(
    "env",
    [
        {"GOOGLE_API_KEY": "k"},
        {"GEMINI_API_KEY": "k"},
        {"GOOGLE_GENAI_USE_VERTEXAI": "TRUE"},
        {"GOOGLE_GENAI_USE_VERTEXAI": "1"},
    ],
)
def test_check_model_config_accepts_any_supported_setup(monkeypatch, env):
    for name in ("GOOGLE_API_KEY", "GEMINI_API_KEY", "GOOGLE_GENAI_USE_VERTEXAI"):
        monkeypatch.delenv(name, raising=False)
    for name, value in env.items():
        monkeypatch.setenv(name, value)

    main_module._check_model_config()


def test_check_model_config_rejects_missing_key(monkeypatch):
    for name in ("GOOGLE_API_KEY", "GEMINI_API_KEY", "GOOGLE_GENAI_USE_VERTEXAI"):
        monkeypatch.delenv(name, raising=False)

    with pytest.raises(SystemExit):
        main_module._check_model_config()


class MainFakeRunner(FakeRunner):
    instances = []

    def __init__(self, agent, app_name):
        super().__init__(MainFakeRunner.replies)
        self.closed = False
        MainFakeRunner.instances.append(self)

    async def close(self):
        self.closed = True


def patch_main(monkeypatch, contexts, replies):
    import google.adk.runners

    monkeypatch.setattr(main_module, "load_dotenv", lambda: None)
    monkeypatch.setenv("GOOGLE_API_KEY", "test-key")
    monkeypatch.delenv("CALENDAR_MAX_EVENTS", raising=False)
    monkeypatch.delenv("CALENDAR_ID", raising=False)
    monkeypatch.setattr(main_module, "get_credentials", lambda: "creds")
    monkeypatch.setattr(main_module, "build_calendar_service", lambda creds: "calendar")
    monkeypatch.setattr(main_module, "build_docs_service", lambda creds: "docs")
    calls = []

    def fake_build_event_contexts(calendar, docs, **kwargs):
        calls.append((calendar, docs, kwargs))
        return contexts

    monkeypatch.setattr(main_module, "build_event_contexts", fake_build_event_contexts)
    MainFakeRunner.instances = []
    MainFakeRunner.replies = replies
    monkeypatch.setattr(google.adk.runners, "InMemoryRunner", MainFakeRunner)
    return calls


def test_main_returns_1_and_closes_runner_when_a_briefing_fails(monkeypatch):
    calls = patch_main(
        monkeypatch,
        [context("A"), context("B")],
        [RuntimeError("boom"), [text_event("ok")]],
    )

    assert asyncio.run(main_module.main()) == 1
    assert MainFakeRunner.instances[0].closed
    assert calls == [
        ("calendar", "docs", {"max_events": 5, "calendar_id": "primary"})
    ]


def test_main_returns_0_when_all_briefings_succeed(monkeypatch):
    patch_main(monkeypatch, [context("A")], [[text_event("ok")]])

    assert asyncio.run(main_module.main()) == 0
    assert MainFakeRunner.instances[0].closed


def test_main_returns_0_without_a_runner_when_there_are_no_events(monkeypatch):
    patch_main(monkeypatch, [], [])

    assert asyncio.run(main_module.main()) == 0
    assert MainFakeRunner.instances == []
