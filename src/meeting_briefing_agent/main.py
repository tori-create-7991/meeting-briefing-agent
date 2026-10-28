"""Run the agent locally: one request, one briefing for the day or upcoming events."""

import argparse
import asyncio
import datetime
import json
import os
import re
import sys

from dotenv import load_dotenv
from google.genai import types

APP_NAME = "meeting_briefing_agent"
USER_ID = "local-user"
WRITER_NAME = "briefing_writer"
MAX_EVENTS_LIMIT = 20

# C0/C1 control characters except tab and newline. Event titles come from
# other people, so strip anything that could drive the terminal.
_CONTROL_CHARS_RE = re.compile(r"[\x00-\x08\x0b-\x1f\x7f-\x9f]")


def _clean(text: str) -> str:
    return _CONTROL_CHARS_RE.sub("", text)


def _date(value: str) -> str:
    try:
        datetime.date.fromisoformat(value)
    except ValueError:
        raise argparse.ArgumentTypeError(f"expected YYYY-MM-DD, got {value!r}") from None
    return value


def _max_events(value: str) -> int:
    try:
        number = int(value)
    except ValueError:
        number = 0
    if not 1 <= number <= MAX_EVENTS_LIMIT:
        raise argparse.ArgumentTypeError(f"expected an integer 1-{MAX_EVENTS_LIMIT}, got {value!r}")
    return number


def parse_args(argv: list[str] | None = None) -> dict:
    parser = argparse.ArgumentParser(description="Draft pre-meeting briefings.")
    parser.add_argument("--date", type=_date, help="day to brief (YYYY-MM-DD); default: upcoming events")
    parser.add_argument("--max-events", type=_max_events, default=5, help="1-20, default 5")
    args = parser.parse_args(argv)
    return {"date": args.date, "max_events": args.max_events}


def _check_model_config() -> None:
    use_vertex = os.getenv("GOOGLE_GENAI_USE_VERTEXAI", "").lower() in ("1", "true")
    has_key = os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")
    if not use_vertex and not has_key:
        raise SystemExit(
            "Neither GOOGLE_API_KEY nor GEMINI_API_KEY is set. Add one to .env "
            "(see README.md), or set GOOGLE_GENAI_USE_VERTEXAI=TRUE to use "
            "Vertex AI instead."
        )


async def generate_briefing(runner, request: dict) -> str:
    session = await runner.session_service.create_session(app_name=APP_NAME, user_id=USER_ID)
    message = types.Content(role="user", parts=[types.Part(text=json.dumps(request))])
    texts: list[str] = []
    async for event in runner.run_async(user_id=USER_ID, session_id=session.id, new_message=message):
        if event.error_code:
            raise RuntimeError(f"model error {event.error_code}: {event.error_message}")
        if event.author == WRITER_NAME and event.content and event.content.parts:
            texts.extend(part.text for part in event.content.parts if part.text)
    if not texts:
        raise RuntimeError("the model returned no briefing text")
    return "".join(texts)


async def main(argv: list[str] | None = None) -> int:
    request = parse_args(argv)
    load_dotenv()
    _check_model_config()

    # Imported after load_dotenv so BRIEFING_* settings from .env take effect.
    from google.adk.runners import InMemoryRunner

    from meeting_briefing_agent.agent import build_root_agent

    runner = InMemoryRunner(agent=build_root_agent(), app_name=APP_NAME)
    try:
        briefing = await generate_briefing(runner, request)
    except Exception as exc:  # noqa: BLE001 - report and exit non-zero
        print(f"[error] Could not generate the briefing: {_clean(str(exc))}", file=sys.stderr)
        return 1
    finally:
        await runner.close()
    print(_clean(briefing))
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
