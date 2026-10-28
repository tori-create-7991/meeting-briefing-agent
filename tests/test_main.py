import asyncio
from types import SimpleNamespace

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
