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
) -> list[dict]:
    now = datetime.datetime.now(datetime.timezone.utc).isoformat()
    response = (
        service.events()
        .list(
            calendarId=calendar_id,
            timeMin=now,
            maxResults=max_results,
            singleEvents=True,
            orderBy="startTime",
            fields=EVENT_LIST_FIELDS,
        )
        .execute(num_retries=2)
    )
    return response.get("items", [])
