import datetime

from googleapiclient.discovery import build

# Only request the fields the pipeline uses. Attendees, organizer and
# conference data are never fetched. The description is still sent to the
# model as written, including any links pasted into it.
EVENT_LIST_FIELDS = (
    "items(summary,start,end,description,attachments(fileId,mimeType))"
)


def build_calendar_service(creds):
    return build("calendar", "v3", credentials=creds)


def fetch_upcoming_events(
    service,
    calendar_id: str = "primary",
    max_results: int = 5,
    time_min: str | None = None,
    time_max: str | None = None,
) -> list[dict]:
    """List events starting from time_min (default: now) up to time_max.

    Times are RFC 3339 strings with an offset.
    """
    params = {
        "calendarId": calendar_id,
        "timeMin": time_min
        or datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "maxResults": max_results,
        "singleEvents": True,
        "orderBy": "startTime",
        "fields": EVENT_LIST_FIELDS,
    }
    if time_max:
        params["timeMax"] = time_max
    response = service.events().list(**params).execute(num_retries=2)
    return response.get("items", [])
