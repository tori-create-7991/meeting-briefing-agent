"""Cloud Run MCP front: exposes get_briefing and forwards to Agent Runtime.

Authentication is Cloud Run IAM (roles/run.invoker); this app has no auth
code of its own. Run with:

    uvicorn meeting_briefing_mcp.server:app --host 0.0.0.0 --port $PORT
"""

import base64
import datetime
import functools
import json
import os

from mcp.server.mcpserver import Context, MCPServer
from mcp.server.mcpserver.exceptions import ToolError

WRITER_NAME = "briefing_writer"
MAX_EVENTS_LIMIT = 20

mcp = MCPServer("meeting-briefing")


def validate_request(date: str | None, max_events: int) -> dict:
    if date is not None:
        try:
            datetime.date.fromisoformat(date)
        except ValueError:
            raise ValueError(f"date must be YYYY-MM-DD, got {date!r}") from None
    if isinstance(max_events, bool) or not 1 <= max_events <= MAX_EVENTS_LIMIT:
        raise ValueError(f"max_events must be 1-{MAX_EVENTS_LIMIT}, got {max_events!r}")
    return {"date": date, "max_events": max_events}


def caller_email(headers) -> str:
    """Email claim of the caller's ID token, used only as a session label.

    Cloud Run IAM has already verified the token before the request reaches
    this app, and the value is never used for authorization.
    """
    auth = (headers or {}).get("authorization", "")
    if not auth.lower().startswith("bearer "):
        return "anonymous"
    parts = auth[7:].split(".")
    if len(parts) != 3:
        return "anonymous"
    try:
        payload = json.loads(base64.urlsafe_b64decode(parts[1] + "=" * (-len(parts[1]) % 4)))
    except (ValueError, json.JSONDecodeError):
        return "anonymous"
    email = payload.get("email") if isinstance(payload, dict) else None
    return email if isinstance(email, str) and email else "anonymous"


@functools.cache
def get_engine():
    import vertexai

    client = vertexai.Client(
        project=os.environ["GOOGLE_CLOUD_PROJECT"],
        location=os.environ["GOOGLE_CLOUD_LOCATION"],
    )
    return client.agent_engines.get(name=os.environ["AGENT_RUNTIME_RESOURCE"])


async def query_agent(request: dict, user_id: str) -> str:
    texts: list[str] = []
    async for event in get_engine().async_stream_query(
        user_id=user_id, message=json.dumps(request)
    ):
        if not isinstance(event, dict):
            continue
        if event.get("error_code"):
            raise RuntimeError(f"agent error {event['error_code']}: {event.get('error_message')}")
        if event.get("author") != WRITER_NAME:
            continue
        for part in (event.get("content") or {}).get("parts") or []:
            if part.get("text"):
                texts.append(part["text"])
    if not texts:
        raise RuntimeError("the agent returned no briefing text")
    return "".join(texts)


@mcp.tool()
async def get_briefing(
    date: str | None = None, max_events: int = 5, ctx: Context | None = None
) -> str:
    """Draft pre-meeting briefings from Google Calendar and linked Google Docs.

    Args:
        date: Day to brief, YYYY-MM-DD in the agent's timezone (Asia/Tokyo by
            default). Omit for upcoming events from now on.
        max_events: Number of events to cover, 1-20.
    """
    # ToolError messages reach the caller; other exceptions would be reduced
    # to a generic "Error executing tool".
    try:
        request = validate_request(date, max_events)
    except ValueError as exc:
        raise ToolError(str(exc)) from exc
    user_id = caller_email(ctx.headers if ctx else None)
    try:
        return await query_agent(request, user_id)
    except Exception as exc:  # noqa: BLE001 - report the cause to the caller
        raise ToolError(f"Agent Runtime call failed: {type(exc).__name__}: {exc}") from exc


def create_app():
    # Cloud Run serves on 0.0.0.0, so the SDK's localhost-only DNS rebinding
    # guard does not apply; Cloud Run IAM rejects unauthenticated requests.
    return mcp.streamable_http_app(stateless_http=True, json_response=True, host="0.0.0.0")


app = create_app()
