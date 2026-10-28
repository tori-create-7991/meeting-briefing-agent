# meeting-briefing-agent

An [ADK](https://google.github.io/adk-docs/) agent that reads your Google
Calendar events, pulls in related Google Docs material, and drafts a short
pre-meeting briefing.

> **Status: Milestone 2.** The agent runs locally, or on Gemini Enterprise
> Agent Platform's Agent Runtime behind a Cloud Run MCP server that Claude
> Code can call. Scheduled runs and past-meeting trends are planned for
> later milestones.

## How it works

```
Claude Code ──(ID token)──▶ Cloud Run: MCP front (get_briefing)
                                   │
                                   ▼
                     Agent Runtime: SequentialAgent
                       ├ ContextFetcher  (no LLM) Calendar + Docs
                       └ BriefingWriter  (Gemini)  one briefing for all events
```

- `ContextFetcher` lists the events for a day (or upcoming events), finds
  linked or attached Google Docs, and reads their text. It sends nothing to
  the model itself.
- `BriefingWriter` writes one briefing with a section per event, in
  `BRIEFING_LANGUAGE`.
- Deployed, the agent reads Workspace through keyless domain-wide
  delegation: no service account key and no stored refresh token.

Deployment: [docs/deploy.md](docs/deploy.md). Design decisions:
[docs/design/m2-agent-platform.md](docs/design/m2-agent-platform.md).

## Run locally

### Prerequisites

- Python 3.10+ on macOS or Linux, and [uv](https://docs.astral.sh/uv/)
- A GCP project of your own with the Google Calendar API and Google Docs
  API enabled
- An OAuth 2.0 **Desktop app** client created in that project, with the
  client secret downloaded as `credentials.json`
- Gemini access: a Gemini API key from
  [AI Studio](https://aistudio.google.com/apikey), or Vertex AI. Read
  [Data handling](#data-handling) before choosing the free tier.

### Install

```bash
uv sync --locked --extra dev
```

`uv.lock` pins every dependency, including transitive ones. Use it rather
than `pip install` so you get the reviewed versions.

### Configure

```bash
cp .env.example .env
```

Fill in `.env`:

```
GOOGLE_API_KEY=<your AI Studio key>
```

`GEMINI_API_KEY` works too. If both are set, `GOOGLE_API_KEY` wins.

| Variable | Default | Meaning |
|---|---|---|
| `BRIEFING_MODEL` | `gemini-3.5-flash` | Gemini model ID |
| `BRIEFING_LANGUAGE` | `ja` | Language the briefing is written in |
| `BRIEFING_TIMEZONE` | `Asia/Tokyo` | Timezone that `--date` refers to |
| `CALENDAR_ID` | `primary` | Calendar to read |
| `WORKSPACE_AUTH` | `local_oauth` | `local_oauth` (browser consent) or `dwd` (domain-wide delegation, used when deployed) |
| `GOOGLE_GENAI_USE_VERTEXAI` | `FALSE` | `TRUE` to call Gemini through Vertex AI instead of an API key |

Place your OAuth client secret at the repo root as `credentials.json`.
`credentials.json`, `client_secret*.json`, `token.json` and `.env` are
gitignored — never commit them.

### Run

```bash
uv run python -m meeting_briefing_agent.main --date 2026-10-29
```

Without `--date`, it briefs upcoming events from now on. `--max-events`
(1-20, default 5) limits how many.

The first run opens a browser window for Google OAuth consent and caches
the resulting token to `token.json` (permissions `0600`). Subsequent runs
reuse it. If the cached token can no longer be refreshed — for example
because your OAuth client is in "Testing" status, where refresh tokens
expire after 7 days — the consent screen opens again automatically.

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
- **Vertex AI** (always used when deployed): covered by the Google Cloud
  terms instead; see
  [Vertex AI data governance](https://cloud.google.com/vertex-ai/generative-ai/docs/data-governance).

Check the current
[Gemini API Additional Terms of Service](https://ai.google.dev/gemini-api/terms)
before use.

Event descriptions and documents can be written by people outside your
organization. The agent treats them as data and has no tools, so it can
only return text; still, read briefings with that in mind.

## Test

```bash
uv run pytest
```

The briefing quality evaluation calls Gemini and is run by hand; see
[tests/eval/README.md](tests/eval/README.md).

## Roadmap

- Scheduled daily briefings and a delivery channel
- Past-meeting-trend context via Vertex AI Memory Bank

## License

MIT — see [LICENSE](LICENSE).
