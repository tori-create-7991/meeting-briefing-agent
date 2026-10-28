import asyncio
import json
from types import SimpleNamespace

import pytest

from meeting_briefing_agent import main as main_module
from meeting_briefing_agent.main import generate_briefing, parse_args


def text_event(text, author="briefing_writer"):
    part = SimpleNamespace(text=text)
    return SimpleNamespace(
        author=author, error_code=None, error_message=None, content=SimpleNamespace(parts=[part])
    )


def error_event(code, message):
    return SimpleNamespace(author="briefing_writer", error_code=code, error_message=message, content=None)


class FakeSessionService:
    async def create_session(self, app_name, user_id):
        return SimpleNamespace(id="session")


class FakeRunner:
    """Replays one scripted reply: a list of events, or an exception."""

    instances = []
    reply = []

    def __init__(self, agent=None, app_name=None):
        self.session_service = FakeSessionService()
        self.messages = []
        self.closed = False
        FakeRunner.instances.append(self)

    async def run_async(self, user_id, session_id, new_message):
        self.messages.append(new_message)
        if isinstance(FakeRunner.reply, Exception):
            raise FakeRunner.reply
        for event in FakeRunner.reply:
            yield event

    async def close(self):
        self.closed = True


def briefing(reply, request=None):
    FakeRunner.reply = reply
    runner = FakeRunner()
    return runner, asyncio.run(generate_briefing(runner, request or {"date": None, "max_events": 5}))


def test_parse_args_builds_the_request():
    assert parse_args(["--date", "2026-10-29"]) == {"date": "2026-10-29", "max_events": 5}
    assert parse_args(["--max-events", "3"]) == {"date": None, "max_events": 3}


@pytest.mark.parametrize("argv", [["--date", "10/29"], ["--max-events", "0"], ["--max-events", "21"]])
def test_parse_args_rejects_bad_values(argv):
    with pytest.raises(SystemExit):
        parse_args(argv)


def test_generate_briefing_sends_request_and_keeps_only_writer_text():
    runner, text = briefing(
        [text_event("fetcher noise", author="context_fetcher"), text_event("本文")],
        {"date": "2026-10-29", "max_events": 3},
    )

    assert text == "本文"
    assert json.loads(runner.messages[0].parts[0].text) == {"date": "2026-10-29", "max_events": 3}


def test_generate_briefing_raises_on_model_error_event():
    with pytest.raises(RuntimeError, match="SAFETY"):
        briefing([error_event("SAFETY", "blocked")])


def test_generate_briefing_raises_when_no_text_comes_back():
    with pytest.raises(RuntimeError, match="no briefing text"):
        briefing([])


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


def patch_main(monkeypatch, reply):
    import google.adk.runners

    monkeypatch.setattr(main_module, "load_dotenv", lambda: None)
    monkeypatch.setenv("GOOGLE_API_KEY", "test-key")
    monkeypatch.setattr(google.adk.runners, "InMemoryRunner", FakeRunner)
    FakeRunner.instances = []
    FakeRunner.reply = reply


def test_main_prints_briefing_and_returns_0(monkeypatch, capsys):
    patch_main(monkeypatch, [text_event("Evil\x1b[2J briefing")])

    assert asyncio.run(main_module.main(["--date", "2026-10-29"])) == 0
    assert FakeRunner.instances[0].closed
    out = capsys.readouterr().out
    assert "briefing" in out and "\x1b" not in out


def test_main_returns_1_and_closes_runner_on_failure(monkeypatch, capsys):
    patch_main(monkeypatch, RuntimeError("quota\x1b[2J"))

    assert asyncio.run(main_module.main([])) == 1
    assert FakeRunner.instances[0].closed
    err = capsys.readouterr().err
    assert "quota" in err and "\x1b" not in err
