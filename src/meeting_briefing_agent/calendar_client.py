import datetime

from googleapiclient.discovery import build


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
        )
        .execute()
    )
    return response.get("items", [])
