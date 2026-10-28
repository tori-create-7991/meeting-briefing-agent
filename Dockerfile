# Cloud Run image for the MCP front (meeting_briefing_mcp). The agent itself
# runs on Agent Runtime from source (scripts/build_agent_source.sh).
FROM python:3.12-slim

COPY --from=ghcr.io/astral-sh/uv:0.11.21 /uv /bin/uv

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Dependencies first so source edits reuse the cached layer.
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

COPY src ./src
RUN uv sync --frozen --no-dev

RUN useradd --uid 10001 --no-create-home app
USER app

CMD ["sh", "-c", "exec /app/.venv/bin/uvicorn meeting_briefing_mcp.server:app --host 0.0.0.0 --port ${PORT:-8080}"]
