# Meeting Briefing Agent — Milestone 1: Local Verification

> **For agent:** REQUIRED SUB-SKILL: Use executing-plans to implement this plan task-by-task.

**Goal:** Build a Python ADK agent that fetches upcoming Google Calendar events, resolves related Google Docs, and drafts a briefing, verified locally via `InMemoryRunner`.
**Architecture:** Imperative fetch-then-hand-to-agent pipeline (Calendar → Docs → assembled context → ADK Agent for prose generation), with a pluggable memory-service factory as the extension point for later Vertex AI Memory Bank wiring.
**Tech Stack:** Python 3.10+, `google-adk`, `google-api-python-client`, `google-auth-oauthlib`, Gemini via AI Studio (`GOOGLE_API_KEY`).

---

## 前提条件

- ✅ Python 3.10 以上（3.14.4 確認済み）
- ✅ pip / venv で仮想環境を作成できること（pip 26.0.1 確認済み）
- ✅ インターネット接続（`pip install google-adk` 等の取得に必要）
- ✅ git（コミット用、リポジトリは init 済み、user.email は noreply アドレス設定済み）
- ⚠️ SKIPPED: `GOOGLE_API_KEY`（Gemini AI Studio）・`credentials.json`（GCP `tori-agent` OAuth Desktopクライアント） — このセッションのコード実装・単体テストには不要。マニュアル実行検証（Verificationセクション）でのみユーザーが用意する。

## Context

Notion task `meeting-briefing-agent` (実装, P2): build an ADK-based agent that
reads Google Calendar events, finds related Google Docs material, and drafts
a pre-meeting briefing. Long-term scope includes Agent Engine deployment,
Cloud Scheduler automation, and Vertex AI Memory Bank for past-meeting
trends — but per grill-me/brainstorming with the user, **this plan covers
only completion condition 1**: local verification via ADK's `InMemoryRunner`
that Calendar fetch → briefing generation works end-to-end. Deployment,
Agent Client OAuth flow, Cloud Scheduler, and real Memory Bank wiring are
explicitly deferred to a future session/task.

Repo is currently empty (no git init, no files) at
`/Users/ryo/Repo/oss/meeting-briefing-agent`. Will be public OSS under MIT
license eventually.

## Decisions from grill-me

- ADK: Python (`google-adk`), not Java.
- Memory Bank: pluggable factory; local uses `InMemoryMemoryService`, Vertex
  wiring deferred (raises `NotImplementedError` for now).
- Related-docs resolution: prefer `event.attachments[]` (Drive fileId),
  else regex-extract `docs.google.com/document/d/...` from description,
  else proceed without material.
- Local auth: OAuth 2.0 Desktop-app flow (`credentials.json` supplied
  manually by user from GCP project `tori-agent`, cached `token.json`),
  both gitignored.
- License: MIT.
- LLM backend: Gemini via AI Studio free tier (`GOOGLE_API_KEY`,
  `GOOGLE_GENAI_USE_VERTEXAI=FALSE`) — not Vertex-billed, since this is
  local-only for now.

## Architecture

Imperative fetch-then-hand-to-agent pipeline (not agent-invoked tools) for
Calendar/Docs access — deterministic, unit-testable without mocking LLM
tool-call decisions, and every event always needs both Calendar+Docs data
(no case where letting the LLM decide adds value). The ADK `Agent` is used
only for the actual briefing-prose generation step, fed pre-assembled
structured context per event. `main.py` orchestrates: auth → fetch events →
resolve+fetch docs → run agent per event via `InMemoryRunner` → print
briefing to stdout.

```
main.py
 ├─ auth.get_credentials()                     # OAuth desktop flow
 ├─ calendar_client.fetch_upcoming_events()     # Calendar API
 ├─ pipeline.build_event_contexts()             # per-event: resolve+fetch docs
 │    ├─ doc_links.resolve_doc_ids()            # attachments > description regex > []
 │    └─ docs_client.fetch_doc_text()           # Docs API, truncated
 ├─ memory.get_memory_service()                 # InMemoryMemoryService (extension point)
 └─ agent.root_agent via InMemoryRunner         # drafts briefing text per event
```

## Files to create

**Scaffolding**
- `pyproject.toml` — src-layout, `meeting_briefing_agent` package, Python
  ≥3.10, deps: `google-adk>=2.5.0`, `google-api-python-client`,
  `google-auth-httplib2`, `google-auth-oauthlib`, `python-dotenv`;
  dev extras: `pytest`, `pytest-asyncio`, `pytest-mock`.
- `.gitignore` — `credentials.json`, `token.json`, `.env`, `__pycache__/`,
  `*.pyc`, `.venv/`, `.pytest_cache/`, `dist/`, `*.egg-info/`.
- `.env.example` — `GOOGLE_API_KEY=`, `GOOGLE_GENAI_USE_VERTEXAI=FALSE`,
  `MEMORY_BACKEND=in_memory`, `CALENDAR_MAX_EVENTS=5`, `CALENDAR_ID=primary`.
- `LICENSE` — MIT, copyright "Ryo Tonegawa", 2026.
- `README.md` — overview + local-only-milestone-1 disclaimer, prerequisites
  (GCP project `tori-agent`, enable Calendar/Docs/Drive APIs, create OAuth
  Desktop client → `credentials.json`, get Gemini API key from AI Studio),
  install/configure/run/test instructions, roadmap note for future
  milestones, and a reminder to set `git config --local user.email` to a
  GitHub noreply address before first commit (public-repo convention).

**Source (`src/meeting_briefing_agent/`)**
- `__init__.py` — package marker.
- `auth.py` — `SCOPES` (calendar.readonly, documents.readonly,
  drive.readonly); `get_credentials(credentials_path, token_path)` —
  loads/refreshes/creates `token.json` via
  `InstalledAppFlow.from_client_secrets_file(...).run_local_server(port=0)`;
  raises clear `FileNotFoundError` if `credentials.json` missing.
- `calendar_client.py` — `build_calendar_service(creds)`;
  `fetch_upcoming_events(service, calendar_id="primary", max_results=5)` via
  `events().list(timeMin=<now>, singleEvents=True, orderBy="startTime")`.
- `doc_links.py` (most test-critical) — `DOC_URL_RE` regex;
  `extract_doc_ids_from_description(description)`;
  `extract_doc_ids_from_attachments(attachments)` (filters
  `application/vnd.google-apps.document` mimeType); `resolve_doc_ids(event)`
  implementing the attachments→description→[] fallback.
- `docs_client.py` — `build_docs_service(creds)`; `fetch_doc_text(service,
  document_id, max_chars=4000)` — walks `body.content` paragraphs/textRun,
  truncates; catches 403/404 and returns `""` with a logged warning so one
  bad doc doesn't kill the run.
- `memory.py` — `get_memory_service()` factory reading `MEMORY_BACKEND` env
  var: `"in_memory"` (default) → `InMemoryMemoryService()`;
  `"vertex_memory_bank"` → `NotImplementedError` with a "future milestone"
  message. Docstring notes this as the swap point.
- `pipeline.py` — `async def build_event_contexts(calendar_service,
  docs_service, max_events=5)` — per event, resolve+fetch up to 2 docs, cap
  prompt size, returns `{"event": {...}, "docs": [...], "past_meeting_trends":
  None}` list (`None` placeholder = Memory Bank hook).
- `agent.py` — `root_agent = Agent(name="meeting_briefing_agent",
  model="gemini-2.5-flash", instruction=<briefing system prompt: agenda
  summary + doc excerpts + "Past meeting trends: not yet available"
  placeholder line>, tools=[])`. No function tool — context is injected
  directly into the user message per event (simpler than a tool wrapper
  since there's no branching for the LLM to decide).
- `main.py` — `async def main()`: `load_dotenv()`, `get_credentials()`,
  build calendar+docs services, `build_event_contexts(...)`, construct
  `InMemoryRunner(agent=root_agent, app_name="meeting_briefing_agent")`,
  create session (awaited), loop events feeding each as `new_message` to
  `runner.run_async(...)`, print briefing text per event.
  `if __name__ == "__main__": asyncio.run(main())`.

**Tests**
- `tests/conftest.py` — fixtures for sample Calendar event payloads (with
  attachments, with description URL, with neither).
- `tests/test_doc_links.py` — `resolve_doc_ids` prefers attachments over
  description; falls back to description when no attachments; returns `[]`
  when neither; description regex matches/no-match; attachment mimetype
  filtering.
- `tests/test_pipeline.py` — mocked `calendar_service`/`docs_client`,
  asserts `build_event_contexts` assembles expected structure and the
  no-material case doesn't raise.

## Not Doing

- Agent Engine deployment — future milestone.
- Agent Client OAuth consent flow (deployed-agent auth, distinct from local
  Desktop OAuth) — future milestone.
- Cloud Scheduler setup — future milestone.
- Real `VertexAiMemoryBankService` wiring — extension point only, raises
  `NotImplementedError` for now.
- GCP infra automation (Terraform, Secret Manager) — `credentials.json` is
  a manually-dropped local file for this milestone.
- Table-aware Google Docs text extraction (nested table content) — flat
  paragraph walk only, noted as a known limitation in code comment.

## Verification

- `pip install -e ".[dev]"` succeeds.
- `pytest` — all tests in `tests/test_doc_links.py` and
  `tests/test_pipeline.py` pass, exit code 0.
- Manual run: user places their own `credentials.json` in repo root, sets
  `GOOGLE_API_KEY` in `.env`, runs `python -m meeting_briefing_agent.main`;
  first run opens a browser OAuth consent screen, subsequent runs reuse
  `token.json`; stdout prints a briefing per upcoming calendar event
  (verified interactively by the user since it requires their real Google
  account — not automatable in this session).
