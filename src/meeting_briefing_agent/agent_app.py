"""Agent Runtime entry point (entrypoint_module / entrypoint_object = app)."""

from vertexai.agent_engines import AdkApp

from meeting_briefing_agent.agent import root_agent

app = AdkApp(agent=root_agent, enable_tracing=True)
