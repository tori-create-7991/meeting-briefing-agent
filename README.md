# meeting-briefing-agent

An [ADK](https://google.github.io/adk-docs/) agent that reads your upcoming
Google Calendar events, pulls in related Google Docs material, and drafts a
short pre-meeting briefing.

> **Status: Milestone 1 (local verification only).** This runs locally via
> ADK's `InMemoryRunner`. Deployment to Vertex AI Agent Engine, Cloud
> Scheduler automation, and real Memory Bank (past-meeting-trends) wiring
> are planned for later milestones and not implemented yet.

## Prerequisites

- Python 3.10+ on macOS or Linux
- [uv](https://docs.astral.sh/uv/)
- A GCP project of your own with the Google Calendar API and Google Docs
  API enabled
- An OAuth 2.0 **Desktop app** client created in that project, with the
  client secret downloaded as `credentials.json`
- A Gemini API key from [AI Studio](https://aistudio.google.com/apikey).
  Read [Data handling](#data-handling) before choosing the free tier.

## Install

```bash
uv sync --locked --extra dev
```

`uv.lock` pins every dependency, including transitive ones. Use it rather
than `pip install` so you get the reviewed versions.

## Configure

```bash
cp .env.example .env
```

Fill in `.env`:

```
GOOGLE_API_KEY=<your AI Studio key>
```

`GEMINI_API_KEY` works too. If both are set, `GOOGLE_API_KEY` wins.

Optional settings:

| Variable | Default | Meaning |
|---|---|---|
| `BRIEFING_MODEL` | `gemini-2.5-flash` | Gemini model ID |
| `CALENDAR_MAX_EVENTS` | `5` | Number of upcoming events (1-50) |
| `CALENDAR_ID` | `primary` | Calendar to read |
| `GOOGLE_GENAI_USE_VERTEXAI` | `FALSE` | `TRUE` to call Gemini through Vertex AI instead of an API key |

Place your OAuth client secret at the repo root as `credentials.json`.
`credentials.json`, `client_secret*.json`, `token.json` and `.env` are
gitignored — never commit them.

## Run

```bash
uv run python -m meeting_briefing_agent.main
```

The first run opens a browser window for Google OAuth consent and caches
the resulting token to `token.json` (permissions `0600`). Subsequent runs
reuse it. If the cached token can no longer be refreshed — for example
because your OAuth client is in "Testing" status, where refresh tokens
expire after 7 days — the consent screen opens again automatically.

The agent prints a briefing for each of your upcoming Calendar events to
stdout. If one event fails (a rate limit, a network error), the others are
still printed and the command exits with status 1.

The agent requests read-only access to Calendar and Docs only. If you ran
an earlier version that also requested Drive access, delete `token.json`
and consent again, then remove the old grant at
[Google Account → Third-party connections](https://myaccount.google.com/connections).

## Data handling

For each event, the agent sends the following to Gemini:

- the event title, start and end time, and description (description
  truncated to 2,000 characters)
- the text of up to two linked or attached Google Docs (each truncated to
  4,000 characters)

It does **not** send the attendees, organizer, conference data or other
structured event fields; those are not even requested from the Calendar
API. The description is sent as written, though, so anything pasted into
it — a video-call link, a passcode, someone's email address — is sent too.

Where that data goes depends on how you call Gemini:

- **Gemini API free tier (AI Studio key without billing):** Google may use
  your prompts and responses to improve its products, and human reviewers
  may read them. Do not use the free tier with calendars or documents that
  contain confidential or other people's personal information.
- **Gemini API paid tier:** prompts are not used to improve Google's
  products, but are logged for a limited time for abuse monitoring.
- **Vertex AI:** covered by the Google Cloud terms instead; see
  [Vertex AI data governance](https://cloud.google.com/vertex-ai/generative-ai/docs/data-governance).

Check the current
[Gemini API Additional Terms of Service](https://ai.google.dev/gemini-api/terms)
before use.

Event descriptions and documents can be written by people outside your
organization. The agent treats them as data and has no tools, so it can
only print text; still, read briefings with that in mind.

## Test

```bash
uv run pytest
```

## Roadmap

- Deploy to Vertex AI Agent Engine
- Keyless Workspace access for the deployed agent
- Daily automated runs via Cloud Scheduler
- Past-meeting-trend context via Vertex AI Memory Bank

## License

MIT — see [LICENSE](LICENSE).
