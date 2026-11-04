"""Agent Runtime entry point (entrypoint_module / entrypoint_object = app).

Event descriptions, document text and the briefing are personal data, so
this app keeps them out of the two places Agent Runtime would otherwise
store them:

- Cloud Trace: ADK puts the full LLM request and response on its spans
  unless ADK_CAPTURE_MESSAGE_CONTENT_IN_SPANS is false. Span names, timings
  and token counts are still recorded.
- Sessions: AdkApp on Agent Runtime defaults to the managed session store,
  which keeps every session (with the fetched text in its state) until it
  is deleted. Each get_briefing call is a single turn, so sessions live in
  memory and end with the request.
"""

import os

from google.adk.sessions import InMemorySessionService
from vertexai.agent_engines import AdkApp

from meeting_briefing_agent.agent import root_agent

os.environ.setdefault("ADK_CAPTURE_MESSAGE_CONTENT_IN_SPANS", "false")


def build_session_service() -> InMemorySessionService:
    return InMemorySessionService()


app = AdkApp(
    agent=root_agent,
    enable_tracing=True,
    session_service_builder=build_session_service,
)
