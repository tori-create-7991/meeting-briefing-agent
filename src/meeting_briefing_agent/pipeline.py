from meeting_briefing_agent.calendar_client import fetch_upcoming_events
from meeting_briefing_agent.doc_links import resolve_doc_ids
from meeting_briefing_agent.docs_client import fetch_doc_text as default_fetch_doc_text

MAX_DOCS_PER_EVENT = 2


async def build_event_contexts(
    calendar_service,
    docs_service,
    max_events: int = 5,
    calendar_id: str = "primary",
    fetch_doc_text=default_fetch_doc_text,
) -> list[dict]:
    events = fetch_upcoming_events(
        calendar_service, calendar_id=calendar_id, max_results=max_events
    )

    contexts = []
    for event in events:
        doc_ids = resolve_doc_ids(event)[:MAX_DOCS_PER_EVENT]
        docs = [
            {"id": doc_id, "text": fetch_doc_text(docs_service, doc_id)}
            for doc_id in doc_ids
        ]
        contexts.append(
            {
                "event": event,
                "docs": docs,
                # Placeholder — populated once VertexAiMemoryBankService is
                # wired in a future milestone.
                "past_meeting_trends": None,
            }
        )
    return contexts
