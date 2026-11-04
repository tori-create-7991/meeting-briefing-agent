"""Agent Runtime entry point (entrypoint_module / entrypoint_object = app).

Event descriptions, document text and the briefing are personal data, so
this app keeps them out of the two places Agent Runtime would otherwise
store them:

- Cloud Trace: tracing is turned on by the GOOGLE_CLOUD_AGENT_ENGINE_ENABLE_TELEMETRY
  env var (set in infra/main/agent_runtime.tf), not by enable_tracing=True.
  With enable_tracing=True, AdkApp.set_up() sets
  ADK_CAPTURE_MESSAGE_CONTENT_IN_SPANS=true and ADK puts the full LLM request
  and response on its spans; otherwise it sets the flag to false. Span names,
  timings and token counts are still recorded.
- Sessions: AdkApp on Agent Runtime defaults to the managed session store,
  which keeps every session (with the fetched text in its state) until it
  is deleted. Each get_briefing call is a single turn, so sessions live in
  memory and end with the request.
"""

from google.adk.sessions import InMemorySessionService
from vertexai.agent_engines import AdkApp

from meeting_briefing_agent.agent import root_agent


def build_session_service() -> InMemorySessionService:
    return InMemorySessionService()


app = AdkApp(agent=root_agent, session_service_builder=build_session_service)
