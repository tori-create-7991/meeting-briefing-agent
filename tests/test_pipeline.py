import asyncio

from meeting_briefing_agent.pipeline import build_event_contexts


class FakeEventsList:
    def __init__(self, items):
        self._items = items

    def execute(self):
        return {"items": self._items}


class FakeEvents:
    def __init__(self, items):
        self._items = items

    def list(self, **kwargs):
        return FakeEventsList(self._items)


class FakeCalendarService:
    def __init__(self, items):
        self._items = items

    def events(self):
        return FakeEvents(self._items)


def test_build_event_contexts_assembles_docs_for_attachment_event(
    event_with_attachment,
):
    calendar_service = FakeCalendarService([event_with_attachment])
    fetched_ids = []

    def fake_fetch_doc_text(service, document_id, max_chars=4000):
        fetched_ids.append(document_id)
        return f"text-for-{document_id}"

    contexts = asyncio.run(
        build_event_contexts(
            calendar_service,
            docs_service=object(),
            max_events=5,
            fetch_doc_text=fake_fetch_doc_text,
        )
    )

    assert len(contexts) == 1
    assert contexts[0]["event"]["summary"] == "Q3 planning"
    assert contexts[0]["docs"] == [
        {"id": "attachment-doc-id", "text": "text-for-attachment-doc-id"}
    ]
    assert contexts[0]["past_meeting_trends"] is None
    assert fetched_ids == ["attachment-doc-id"]


def test_build_event_contexts_no_material_does_not_raise(event_with_no_material):
    calendar_service = FakeCalendarService([event_with_no_material])

    contexts = asyncio.run(
        build_event_contexts(
            calendar_service,
            docs_service=object(),
            max_events=5,
            fetch_doc_text=lambda *a, **kw: "unused",
        )
    )

    assert len(contexts) == 1
    assert contexts[0]["docs"] == []
    assert contexts[0]["past_meeting_trends"] is None


def test_build_event_contexts_caps_docs_per_event_at_two():
    event = {
        "summary": "Many docs",
        "description": "",
        "attachments": [
            {"fileId": f"doc-{i}", "mimeType": "application/vnd.google-apps.document"}
            for i in range(5)
        ],
    }
    calendar_service = FakeCalendarService([event])

    contexts = asyncio.run(
        build_event_contexts(
            calendar_service,
            docs_service=object(),
            max_events=5,
            fetch_doc_text=lambda service, document_id, max_chars=4000: document_id,
        )
    )

    assert len(contexts[0]["docs"]) == 2
