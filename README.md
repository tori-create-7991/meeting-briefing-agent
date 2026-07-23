# meeting-briefing-agent

An [ADK](https://google.github.io/adk-docs/) agent that reads your upcoming
Google Calendar events, pulls in related Google Docs material, and drafts a
short pre-meeting briefing.

> **Status: Milestone 1 (local verification only).** This runs locally via
> ADK's `InMemoryRunner`. Deployment to Vertex AI Agent Engine, Cloud
> Scheduler automation, and real Memory Bank (past-meeting-trends) wiring
> are planned for later milestones and not implemented yet.

## Prerequisites

- Python 3.10+
- A GCP project with the Calendar, Docs, and Drive APIs enabled (this
  project was built against `tori-agent`)
- An OAuth 2.0 **Desktop app** client created in that project, with the
  client secret downloaded as `credentials.json`
- A Gemini API key from [AI Studio](https://aistudio.google.com/apikey)
  (free tier) — this project talks to Gemini directly, not via
  Vertex AI, so no billing setup is required for local use

## Install

```bash
pip install -e ".[dev]"
```

## Configure

```bash
cp .env.example .env
```

Fill in `.env`:

```
GOOGLE_API_KEY=<your AI Studio key>
```

Place your OAuth client secret at the repo root as `credentials.json`.
Both `credentials.json` and the `token.json` generated on first run are
gitignored — never commit them.

## Run

```bash
python -m meeting_briefing_agent.main
```

The first run opens a browser window for Google OAuth consent and caches
the resulting token to `token.json`. Subsequent runs reuse it. The agent
prints a briefing for each of your upcoming Calendar events to stdout.

## Test

```bash
pytest
```

## Roadmap

- Deploy to Vertex AI Agent Engine
- OAuth consent flow via the deployed Agent Client
- Daily automated runs via Cloud Scheduler
- Wire `VertexAiMemoryBankService` for past-meeting-trend context (the
  `memory.py` factory already has an extension point for this)

## License

MIT — see [LICENSE](LICENSE).
