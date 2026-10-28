"""ContextFetcher: deterministic, LLM-free first step of the pipeline.

Reads the request JSON ({"date": "YYYY-MM-DD" | null, "max_events": int})
from the user message, collects events and doc text, and stores them in
session state as `briefing_contexts` for BriefingWriter.
"""

import asyncio
import json
import os
from collections.abc import AsyncGenerator, Callable

from google.adk.agents import BaseAgent
from google.adk.agents.invocation_context import InvocationContext
from google.adk.events import Event, EventActions
from google.auth.exceptions import RefreshError, TransportError

from meeting_briefing_agent.calendar_client import build_calendar_service
from meeting_briefing_agent.credentials import get_workspace_credentials
from meeting_briefing_agent.docs_client import build_docs_service
from meeting_briefing_agent.pipeline import build_event_contexts

STATE_KEY = "briefing_contexts"
DEFAULT_MAX_EVENTS = 5
MAX_EVENTS_LIMIT = 20


def build_contexts_from_workspace(date: str | None, max_events: int) -> list[dict]:
    creds = get_workspace_credentials()
    try:
        return build_event_contexts(
            build_calendar_service(creds),
            build_docs_service(creds),
            max_events=max_events,
            calendar_id=os.getenv("CALENDAR_ID", "primary"),
            date=date,
        )
    except TransportError as exc:
        if "signBlob" in str(exc):
            raise RuntimeError(
                "The agent identity cannot sign as the workspace-reader service "
                "account. Grant it iam.serviceAccounts.signBlob on that account "
                f"(infra/main/iam.tf). Cause: {exc}"
            ) from exc
        raise
    except RefreshError as exc:
        if "unauthorized_client" in str(exc):
            raise RuntimeError(
                "Domain-wide delegation is not authorized. In the Workspace Admin "
                "console, allow the workspace-reader client ID (terraform output "
                "workspace_reader_client_id) the calendar.readonly and "
                f"documents.readonly scopes. Cause: {exc}"
            ) from exc
        raise


def parse_request(text: str | None) -> dict:
    """Parse the request; anything unreadable falls back to defaults."""
    try:
        raw = json.loads(text or "{}")
    except json.JSONDecodeError:
        raw = {}
    if not isinstance(raw, dict):
        raw = {}
    date = raw.get("date") or None
    max_events = raw.get("max_events", DEFAULT_MAX_EVENTS)
    if not isinstance(max_events, int) or isinstance(max_events, bool):
        max_events = DEFAULT_MAX_EVENTS
    max_events = min(max(max_events, 1), MAX_EVENTS_LIMIT)
    return {"date": date if isinstance(date, str) else None, "max_events": max_events}


def _user_text(ctx: InvocationContext) -> str | None:
    content = ctx.user_content
    if not content or not content.parts:
        return None
    return "".join(part.text for part in content.parts if part.text)


class ContextFetcher(BaseAgent):
    # Injected in tests; defaults to the real Workspace collection.
    build_contexts: Callable[[str | None, int], list[dict]] | None = None

    async def _run_async_impl(
        self, ctx: InvocationContext
    ) -> AsyncGenerator[Event, None]:
        request = parse_request(_user_text(ctx))
        build = self.build_contexts or build_contexts_from_workspace
        # The Google API clients block, so keep them off the event loop.
        contexts = await asyncio.to_thread(build, request["date"], request["max_events"])
        yield Event(
            author=self.name,
            invocation_id=ctx.invocation_id,
            branch=ctx.branch,
            actions=EventActions(
                state_delta={STATE_KEY: json.dumps(contexts, ensure_ascii=False)}
            ),
        )
