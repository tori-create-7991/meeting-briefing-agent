import asyncio
import json
import os

from dotenv import load_dotenv
from google.adk.runners import InMemoryRunner
from google.genai import types

from meeting_briefing_agent.agent import root_agent
from meeting_briefing_agent.auth import get_credentials
from meeting_briefing_agent.calendar_client import build_calendar_service
from meeting_briefing_agent.docs_client import build_docs_service
from meeting_briefing_agent.pipeline import build_event_contexts

APP_NAME = "meeting_briefing_agent"
USER_ID = "local-user"


async def main() -> None:
    load_dotenv()

    creds = get_credentials()
    calendar_service = build_calendar_service(creds)
    docs_service = build_docs_service(creds)

    max_events = int(os.getenv("CALENDAR_MAX_EVENTS", "5"))
    calendar_id = os.getenv("CALENDAR_ID", "primary")
    contexts = await build_event_contexts(
        calendar_service, docs_service, max_events=max_events, calendar_id=calendar_id
    )

    if not contexts:
        print("No upcoming events found.")
        return

    runner = InMemoryRunner(agent=root_agent, app_name=APP_NAME)

    for context in contexts:
        # A fresh session per event keeps each briefing generation isolated
        # from the others — otherwise later events' prompts would carry the
        # full conversation history of earlier ones.
        session = await runner.session_service.create_session(
            app_name=APP_NAME, user_id=USER_ID
        )
        message = types.Content(
            role="user", parts=[types.Part(text=json.dumps(context))]
        )
        summary = context["event"].get("summary", "(no title)")
        print(f"\n=== Briefing: {summary} ===")
        async for event in runner.run_async(
            user_id=USER_ID, session_id=session.id, new_message=message
        ):
            if event.content and event.content.parts:
                for part in event.content.parts:
                    if part.text:
                        print(part.text)


if __name__ == "__main__":
    asyncio.run(main())
