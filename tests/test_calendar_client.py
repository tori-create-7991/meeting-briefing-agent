from unittest.mock import MagicMock

from meeting_briefing_agent.calendar_client import fetch_upcoming_events


def make_service(items=None):
    service = MagicMock()
    service.events.return_value.list.return_value.execute.return_value = {
        "items": items or []
    }
    return service


def test_fetch_upcoming_events_passes_time_window():
    service = make_service([{"summary": "a"}])

    events = fetch_upcoming_events(
        service,
        time_min="2026-10-29T00:00:00+09:00",
        time_max="2026-10-30T00:00:00+09:00",
    )

    kwargs = service.events.return_value.list.call_args.kwargs
    assert kwargs["timeMin"] == "2026-10-29T00:00:00+09:00"
    assert kwargs["timeMax"] == "2026-10-30T00:00:00+09:00"
    assert events == [{"summary": "a"}]


def test_fetch_upcoming_events_defaults_to_now_without_upper_bound():
    service = make_service()

    fetch_upcoming_events(service)

    kwargs = service.events.return_value.list.call_args.kwargs
    assert kwargs["timeMin"].endswith("+00:00")
    assert "timeMax" not in kwargs
