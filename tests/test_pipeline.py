from meeting_briefing_agent.calendar_client import EVENT_LIST_FIELDS
import pytest

from meeting_briefing_agent.pipeline import (
    MAX_DESCRIPTION_CHARS,
    build_event_contexts,
    day_window,
    project_event,
)


class FakeEventsList:
    def __init__(self, items):
        self._items = items
        self.num_retries = None

    def execute(self, num_retries=0):
        self.num_retries = num_retries
        return {"items": self._items}


class FakeEvents:
    def __init__(self, items):
        self._items = items
        self.list_kwargs = None

    def list(self, **kwargs):
        self.list_kwargs = kwargs
        self.last_list = FakeEventsList(self._items)
        return self.last_list


class FakeCalendarService:
    def __init__(self, items):
        self._events = FakeEvents(items)

    def events(self):
        return self._events


def test_build_event_contexts_assembles_docs_for_attachment_event(
    event_with_attachment,
):
    calendar_service = FakeCalendarService([event_with_attachment])
    fetched_ids = []

    def fake_fetch_doc_text(service, document_id, max_chars=4000):
        fetched_ids.append(document_id)
        return f"text-for-{document_id}"

    contexts = build_event_contexts(
        calendar_service,
        docs_service=object(),
        max_events=5,
        fetch_doc_text=fake_fetch_doc_text,
    )

    assert len(contexts) == 1
    assert contexts[0]["event"]["summary"] == "Q3 planning"
    assert contexts[0]["docs"] == [
        {"id": "attachment-doc-id", "text": "text-for-attachment-doc-id"}
    ]
    assert contexts[0]["past_meeting_trends"] is None
    assert fetched_ids == ["attachment-doc-id"]


def test_event_list_fields_never_request_people_or_conference_data():
    assert EVENT_LIST_FIELDS == (
        "items(summary,start,end,description,attachments(fileId,mimeType))"
    )
    for field in ("attendees", "organizer", "creator", "conferenceData", "hangoutLink"):
        assert field not in EVENT_LIST_FIELDS


def test_build_event_contexts_requests_limited_fields_with_retries():
    calendar_service = FakeCalendarService([])

    build_event_contexts(calendar_service, docs_service=object())

    events = calendar_service.events()
    assert events.list_kwargs["fields"] == EVENT_LIST_FIELDS
    assert events.last_list.num_retries == 2


def test_build_event_contexts_sends_only_allowlisted_event_fields():
    event = {
        "summary": "Vendor call",
        "start": {"dateTime": "2026-10-29T10:00:00+09:00"},
        "end": {"dateTime": "2026-10-29T11:00:00+09:00"},
        "description": "Agenda",
        "attendees": [{"email": "someone@example.com"}],
        "organizer": {"email": "boss@example.com"},
        "hangoutLink": "https://meet.google.com/abc",
        "attachments": [],
    }

    contexts = build_event_contexts(
        FakeCalendarService([event]),
        docs_service=object(),
        fetch_doc_text=lambda *a, **kw: "unused",
    )

    assert set(contexts[0]["event"]) == {"summary", "start", "end", "description"}


def test_project_event_truncates_long_description():
    view = project_event({"description": "x" * (MAX_DESCRIPTION_CHARS + 10)})

    assert view["description"] == "x" * MAX_DESCRIPTION_CHARS + "…"


def test_build_event_contexts_marks_failed_doc_and_keeps_going():
    doc = "application/vnd.google-apps.document"
    events = [
        {
            "summary": "Two docs",
            "attachments": [
                {"fileId": "broken", "mimeType": doc},
                {"fileId": "ok", "mimeType": doc},
            ],
        },
        {"summary": "Next event", "attachments": []},
    ]

    def fake_fetch_doc_text(service, document_id, max_chars=4000):
        return None if document_id == "broken" else "body"

    contexts = build_event_contexts(
        FakeCalendarService(events),
        docs_service=object(),
        fetch_doc_text=fake_fetch_doc_text,
    )

    assert contexts[0]["docs"] == [
        {"id": "broken", "error": "fetch_failed"},
        {"id": "ok", "text": "body"},
    ]
    assert contexts[1]["event"]["summary"] == "Next event"


def test_build_event_contexts_no_material_does_not_raise(event_with_no_material):
    contexts = build_event_contexts(
        FakeCalendarService([event_with_no_material]),
        docs_service=object(),
        max_events=5,
        fetch_doc_text=lambda *a, **kw: "unused",
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

    contexts = build_event_contexts(
        FakeCalendarService([event]),
        docs_service=object(),
        max_events=5,
        fetch_doc_text=lambda service, document_id, max_chars=4000: document_id,
    )

    assert len(contexts[0]["docs"]) == 2


def test_day_window_covers_the_whole_day_in_the_timezone():
    assert day_window("2026-10-29", "Asia/Tokyo") == (
        "2026-10-29T00:00:00+09:00",
        "2026-10-30T00:00:00+09:00",
    )


def test_day_window_rejects_bad_date():
    with pytest.raises(ValueError):
        day_window("10/29", "Asia/Tokyo")


def test_build_event_contexts_with_date_lists_only_that_day(monkeypatch):
    monkeypatch.delenv("BRIEFING_TIMEZONE", raising=False)
    calendar_service = FakeCalendarService([])

    build_event_contexts(calendar_service, docs_service=object(), date="2026-10-29")

    kwargs = calendar_service.events().list_kwargs
    assert kwargs["timeMin"] == "2026-10-29T00:00:00+09:00"
    assert kwargs["timeMax"] == "2026-10-30T00:00:00+09:00"


def test_build_event_contexts_without_date_has_no_upper_bound():
    calendar_service = FakeCalendarService([])

    build_event_contexts(calendar_service, docs_service=object())

    assert "timeMax" not in calendar_service.events().list_kwargs
