import datetime
import os
from zoneinfo import ZoneInfo

from meeting_briefing_agent.calendar_client import fetch_upcoming_events
from meeting_briefing_agent.doc_links import resolve_doc_ids
from meeting_briefing_agent.docs_client import fetch_doc_text as default_fetch_doc_text

DEFAULT_TIMEZONE = "Asia/Tokyo"
MAX_DOCS_PER_EVENT = 2
MAX_DESCRIPTION_CHARS = 2000

# The only event fields sent to the model. Keep in sync with agent.INSTRUCTION.
EVENT_FIELDS = ("summary", "start", "end", "description")


def project_event(event: dict) -> dict:
    """Reduce a Calendar event to the allowlisted fields sent to the model."""
    view = {key: event[key] for key in EVENT_FIELDS if key in event}
    description = view.get("description")
    if description and len(description) > MAX_DESCRIPTION_CHARS:
        view["description"] = description[:MAX_DESCRIPTION_CHARS] + "…"
    return view


def day_window(date: str, tz: str) -> tuple[str, str]:
    """Return RFC 3339 start/end of the given YYYY-MM-DD day in timezone tz."""
    day = datetime.date.fromisoformat(date)  # ValueError on a bad date
    zone = ZoneInfo(tz)
    start = datetime.datetime.combine(day, datetime.time(), tzinfo=zone)
    end = datetime.datetime.combine(
        day + datetime.timedelta(days=1), datetime.time(), tzinfo=zone
    )
    return start.isoformat(), end.isoformat()


def build_event_contexts(
    calendar_service,
    docs_service,
    max_events: int = 5,
    calendar_id: str = "primary",
    fetch_doc_text=default_fetch_doc_text,
    date: str | None = None,
    tz: str | None = None,
) -> list[dict]:
    """Collect events and their related doc text.

    With date (YYYY-MM-DD), only events on that day in tz are listed (tz
    defaults to BRIEFING_TIMEZONE, then Asia/Tokyo). Without it, upcoming
    events from now on are listed.

    Synchronous and blocking (the Google API clients are); async callers
    should run it with asyncio.to_thread.
    """
    time_min = time_max = None
    if date:
        tz = tz or os.getenv("BRIEFING_TIMEZONE", DEFAULT_TIMEZONE)
        time_min, time_max = day_window(date, tz)
    events = fetch_upcoming_events(
        calendar_service,
        calendar_id=calendar_id,
        max_results=max_events,
        time_min=time_min,
        time_max=time_max,
    )

    contexts = []
    for event in events:
        doc_ids = resolve_doc_ids(event)[:MAX_DOCS_PER_EVENT]
        docs = []
        for doc_id in doc_ids:
            text = fetch_doc_text(docs_service, doc_id)
            if text is None:
                docs.append({"id": doc_id, "error": "fetch_failed"})
            else:
                docs.append({"id": doc_id, "text": text})
        contexts.append(
            {
                "event": project_event(event),
                "docs": docs,
                # Placeholder — populated once a memory backend is wired in
                # a future milestone.
                "past_meeting_trends": None,
            }
        )
    return contexts
