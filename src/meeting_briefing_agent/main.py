import asyncio
import json
import os
import re
import sys

from dotenv import load_dotenv
from google.genai import types

from meeting_briefing_agent.auth import get_credentials
from meeting_briefing_agent.calendar_client import build_calendar_service
from meeting_briefing_agent.docs_client import build_docs_service
from meeting_briefing_agent.pipeline import build_event_contexts

APP_NAME = "meeting_briefing_agent"
USER_ID = "local-user"

# C0/C1 control characters except tab and newline. Event titles come from
# other people, so strip anything that could drive the terminal.
_CONTROL_CHARS_RE = re.compile(r"[\x00-\x08\x0b-\x1f\x7f-\x9f]")


def _clean(text: str) -> str:
    return _CONTROL_CHARS_RE.sub("", text)


def _read_max_events() -> int:
    raw = os.getenv("CALENDAR_MAX_EVENTS", "5")
    try:
        value = int(raw)
    except ValueError:
        value = 0
    if not 1 <= value <= 50:
        raise SystemExit(f"CALENDAR_MAX_EVENTS must be an integer 1-50, got {raw!r}")
    return value


def _check_model_config() -> None:
    use_vertex = os.getenv("GOOGLE_GENAI_USE_VERTEXAI", "").lower() in ("1", "true")
    if not use_vertex and not os.getenv("GOOGLE_API_KEY"):
        raise SystemExit(
            "GOOGLE_API_KEY is not set. Add it to .env (see README.md), or set "
            "GOOGLE_GENAI_USE_VERTEXAI=TRUE to use Vertex AI instead."
        )


async def generate_briefing(runner, context: dict) -> str:
    # A fresh session per event keeps each briefing generation isolated
    # from the others — otherwise later events' prompts would carry the
    # full conversation history of earlier ones.
    session = await runner.session_service.create_session(
        app_name=APP_NAME, user_id=USER_ID
    )
    message = types.Content(role="user", parts=[types.Part(text=json.dumps(context))])
    texts: list[str] = []
    async for event in runner.run_async(
        user_id=USER_ID, session_id=session.id, new_message=message
    ):
        if event.error_code:
            raise RuntimeError(f"model error {event.error_code}: {event.error_message}")
        if event.content and event.content.parts:
            texts.extend(part.text for part in event.content.parts if part.text)
    if not texts:
        raise RuntimeError("the model returned no briefing text")
    return "".join(texts)


async def run_briefings(runner, contexts: list[dict], out=print) -> int:
    """Print a briefing per event; return how many events failed.

    One failing event (rate limit, network error, ...) does not stop the
    others.
    """
    failures = 0
    for context in contexts:
        summary = context["event"].get("summary", "(no title)")
        out(f"\n=== Briefing: {_clean(summary)} ===")
        try:
            briefing = await generate_briefing(runner, context)
        except Exception as exc:  # noqa: BLE001 - report and keep going
            failures += 1
            out(f"[error] Could not generate this briefing: {exc}")
            continue
        out(_clean(briefing))
    return failures


async def main() -> int:
    load_dotenv()
    _check_model_config()
    max_events = _read_max_events()
    calendar_id = os.getenv("CALENDAR_ID", "primary")

    # Imported after load_dotenv so BRIEFING_MODEL from .env takes effect.
    from google.adk.runners import InMemoryRunner

    from meeting_briefing_agent.agent import root_agent

    creds = get_credentials()
    calendar_service = build_calendar_service(creds)
    docs_service = build_docs_service(creds)

    contexts = await asyncio.to_thread(
        build_event_contexts,
        calendar_service,
        docs_service,
        max_events=max_events,
        calendar_id=calendar_id,
    )

    if not contexts:
        print("No upcoming events found.")
        return 0

    runner = InMemoryRunner(agent=root_agent, app_name=APP_NAME)
    try:
        failures = await run_briefings(runner, contexts)
    finally:
        await runner.close()

    if failures:
        print(f"\n{failures} of {len(contexts)} briefings failed.", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
