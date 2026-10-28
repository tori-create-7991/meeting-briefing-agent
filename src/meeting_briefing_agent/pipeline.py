from meeting_briefing_agent.calendar_client import fetch_upcoming_events
from meeting_briefing_agent.doc_links import resolve_doc_ids
from meeting_briefing_agent.docs_client import fetch_doc_text as default_fetch_doc_text

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


def build_event_contexts(
    calendar_service,
    docs_service,
    max_events: int = 5,
    calendar_id: str = "primary",
    fetch_doc_text=default_fetch_doc_text,
) -> list[dict]:
    """Collect events and their related doc text.

    Synchronous and blocking (the Google API clients are); async callers
    should run it with asyncio.to_thread.
    """
    events = fetch_upcoming_events(
        calendar_service, calendar_id=calendar_id, max_results=max_events
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
