# Deploy: Cloud Run MCP front + Agent Runtime

This guide deploys milestone 2: Claude Code calls the MCP tool
`get_briefing` on Cloud Run, which queries the agent on Agent Runtime. The
agent reads one Workspace user's Calendar and Docs through keyless
domain-wide delegation. Design: [design/m2-agent-platform.md](design/m2-agent-platform.md).

```
Claude Code ──(ID token)──▶ Cloud Run: mcp-front ──▶ Agent Runtime: SequentialAgent
                                                          │ signBlob as workspace-reader
                                                          ▼
                                             Calendar / Docs of workspace_subject
```

Real IDs (organization, billing account, project, email addresses) go only
into `infra/*/terraform.tfvars`, which is gitignored.

## Prerequisites

- A Google Workspace organization, and in it:
  - permission to create projects and link a billing account
    (Project Creator, Billing Account User)
  - a super admin who can authorize domain-wide delegation
- `gcloud`, `terraform` 1.6+, `uv`
- This repository checked out, with `uv sync --locked --extra dev` done

## 1. Sign in

```bash
gcloud auth login
```

```bash
gcloud auth application-default login
```

Terraform uses the application default credentials.

## 2. Create the project (`infra/bootstrap`)

```bash
cp infra/bootstrap/terraform.tfvars.example infra/bootstrap/terraform.tfvars
```

Fill in `project_id`, `org_id` and `billing_account`, then:

```bash
terraform -chdir=infra/bootstrap init
```

```bash
terraform -chdir=infra/bootstrap plan
```

Check the plan: it creates the project, links billing, and creates the
state bucket. Then apply:

```bash
terraform -chdir=infra/bootstrap apply
```

The project has `deletion_policy = "PREVENT"`. See [Tear down](#tear-down).

## 3. Package the agent

```bash
scripts/build_agent_source.sh
```

This writes `dist/agent_source.tar.gz` (the agent package and a pinned
`requirements.txt`) and `dist/class_methods.json` (the methods Agent Runtime
exposes). Run it again whenever the agent code or dependencies change.

## 4. First apply of `infra/main`

```bash
cp infra/main/terraform.tfvars.example infra/main/terraform.tfvars
```

Fill in `project_id`, `org_id`, `workspace_subject` (the Workspace user whose
calendar is read) and `invoker_members` (who may call the MCP front, for
example `["user:me@example.org"]`). Leave `mcp_image` unset for now: the
first apply uses a public placeholder image.

```bash
terraform -chdir=infra/main init -backend-config=bucket="$(terraform -chdir=infra/bootstrap output -raw tfstate_bucket)"
```

```bash
terraform -chdir=infra/main plan
```

```bash
terraform -chdir=infra/main apply
```

Creating the Agent Runtime instance takes several minutes.

## 5. Build the MCP front image and apply again

```bash
scripts/build_mcp_image.sh <project_id> us-central1 v1
```

The build runs as the `mcp-builder` service account from step 4, not the
Compute Engine default one (new projects give that one no roles). It stages
the source and logs in the `<project_id>-build` bucket, which deletes them
after 7 days.

Set `mcp_image` in `infra/main/terraform.tfvars` to the image the script
printed, then:

```bash
terraform -chdir=infra/main apply
```

## 6. Authorize domain-wide delegation

```bash
terraform -chdir=infra/main output -raw workspace_reader_client_id
```

In the Google Admin console, go to **Security → Access and data control →
API controls → Manage Domain Wide Delegation → Add new**, enter that client
ID, and these scopes:

```
https://www.googleapis.com/auth/calendar.readonly,https://www.googleapis.com/auth/documents.readonly
```

The `workspace-reader` service account has no key and no GCP roles. Only the
agent's identity can sign as it, and only for these two read-only scopes.

What this grant allows: anyone who can sign as `workspace-reader` can read
the calendar and documents of **any** user in the domain, read-only. The
agent always names `workspace_subject`, but that is a setting, not a limit
Google enforces. Signing is granted to the agent's identity only, yet
project Owners can grant it to themselves. Keep this project dedicated to
the agent and its Owners few.

## 7. Register the MCP server in Claude Code

```bash
terraform -chdir=infra/main output -raw mcp_url
```

Claude Code gets the Authorization header from `scripts/mcp_headers.sh`
(its `headersHelper`), which prints your Google ID token. Copy the script
to a stable place first: Claude Code runs it by absolute path, and a path
inside a temporary worktree breaks once that worktree is removed.

```bash
mkdir -p ~/.claude/bin && cp scripts/mcp_headers.sh ~/.claude/bin/briefing-mcp-headers.sh
```

Register the server in **user scope**, with your account (the one in
`invoker_members`) pinned:

```bash
claude mcp add-json meeting-briefing '{"type":"http","url":"<mcp_url>","headersHelper":"'"$HOME"'/.claude/bin/briefing-mcp-headers.sh --account me@example.org"}' --scope user
```

How the helper behaves:

- Claude Code runs it when connecting and reconnecting, and again
  automatically after a 401 or 403, then retries the tool call once. The ID
  token expires after an hour; this refresh needs no setup.
- It must finish within 10 seconds; `gcloud` takes 1-2.
- `--account` picks the gcloud account even when another gcloud
  configuration is active. Without it, the active account is used.
- The helper may run without your login shell's `PATH`. The script finds
  `gcloud` and a Python 3.10+ for it (PATH, then mise and Homebrew
  locations); pass `--gcloud /path/to/gcloud` if it still cannot.
- User scope matters: for a project `.mcp.json`, Claude Code strips
  environment variables whose names contain `TOKEN`, `KEY` or `AUTH` and
  runs the helper in the project directory.

To call as a service account instead of yourself, add it to
`invoker_members` (`serviceAccount:...`), grant yourself
`roles/iam.serviceAccountTokenCreator` on it, and use
`--impersonate <service account email>` instead of `--account`. The script
then requests a token whose audience is the Cloud Run URL.

## 8. Check it works

Ask Claude Code something like "brief me on my meetings on 2026-10-29". It
calls `get_briefing(date="2026-10-29")` and returns the briefing.

Each run is traced: open **Trace Explorer** in the Cloud console for the
project and look for the agent's spans (`context_fetcher` and
`briefing_writer`, with timings and token counts). The MCP front's request
is a separate trace.

The briefing summarizes text that other people wrote: invitation
descriptions and shared documents. Treat it as data, not as instructions,
when you ask Claude Code to act on it.

## What is stored where

| Place | What | Kept for | Removed by |
|---|---|---|---|
| Agent Runtime sessions | Nothing. Sessions live in memory for one call (`agent_app.py`) | The call | The call ending |
| Cloud Trace | Span names, timings, token counts, model name. Not the prompt or the response: `agent_app.py` sets `ADK_CAPTURE_MESSAGE_CONTENT_IN_SPANS=false` | 30 days | Expiry |
| Cloud Logging | Errors with tracebacks, IDs of documents that could not be fetched, Google API error text. Not event or document text | 30 days (`_Default` bucket) | Expiry |
| Gemini on Vertex AI | The prompt for each call: event titles, times, descriptions and document text | See [Vertex AI data governance](https://cloud.google.com/vertex-ai/generative-ai/docs/data-governance) | — |
| `<project_id>-build` bucket | Source uploads and logs of MCP front builds (no Workspace data) | 7 days | Lifecycle rule |

Anyone with a viewer role on the project can read the traces and logs.

## Updating

| Changed | Run |
|---|---|
| Agent code or dependencies | `scripts/build_agent_source.sh`, then `terraform -chdir=infra/main apply` |
| MCP front code | `scripts/build_mcp_image.sh <project_id> us-central1 <new tag>`, set `mcp_image`, then apply |
| Model, language, timezone | `briefing_model`, `briefing_model_location`, `briefing_language`, `briefing_timezone` in `terraform.tfvars`, then apply |
| Agent instance size | `agent_cpu`, `agent_memory` in `terraform.tfvars`, then apply |

Agent source updates change the Agent Runtime instance in place (checked
2026-10-29 and 2026-11-04), so the agent's identity and its IAM grants stay.

## Rolling back

- **MCP front**: set `mcp_image` to the previous tag and apply. The image
  repository keeps the 3 newest versions and anything younger than 7 days;
  if the tag is gone, check out its commit and build it again.
- **Agent**: check out the previous commit, run
  `scripts/build_agent_source.sh`, then apply.
- **After a destroy and a new apply**: `workspace-reader` gets a new client
  ID, so add it again in the Admin console (step 6) and remove the old
  entry. The agent's identity changes with the new instance; Terraform
  grants the new one again.

## Troubleshooting

| Symptom in the tool result | Fix |
|---|---|
| `/mcp` shows the server as failed to connect | The token was rejected at connect time. Run the helper command by hand to see gcloud's error, fix it (sign in again, `--account`, `--gcloud`), then reconnect from `/mcp` |
| `/mcp` shows the server as needing authentication | A new token was still refused: the account is not in `invoker_members`, or `--account` names another account |
| "cannot sign as the workspace-reader service account" with `401 UNAUTHENTICATED` | The Agent Identity token is bound to the agent's certificate and was sent without mTLS. `credentials.py` signs over an mTLS session; make sure the deployed source is current (`scripts/build_agent_source.sh`, then apply) |
| "cannot sign as the workspace-reader service account" with `403` | Agent Identity could not get `signBlob`. Set `runtime_identity = "service_account"` and apply: the agent then runs as the dedicated `briefing-runtime` service account |
| "Domain-wide delegation is not authorized" | Step 6 is missing, or the client ID or scopes differ |
| `Publisher model ... was not found` | The model is not served from `briefing_model_location`. Gemini 3 models are served only from `global` (the default); older ones may be retired for new projects. Set `briefing_model` and `briefing_model_location` to a pair that answers, then apply |
| `aiplatform.reasoningEngines...` permission denied | Add the missing permission to the `briefingQueryAgent` role in `infra/main/iam.tf` |
| The agent restarts or runs out of memory | Raise `agent_memory` (for example `"4Gi"`) and apply |
| `apply` rejects `min_instances = 0` | Set `agent_min_instances = 1` (the agent then bills while idle) |
| Cloud Build: `...-compute@developer.gserviceaccount.com does not have storage.objects.get access` | The build ran as the Compute Engine default account. Apply `infra/main` (it creates `mcp-builder` and the build bucket) and build with `scripts/build_mcp_image.sh`, which passes them |
| Cloud Build cannot push the image | Check that `mcp-builder` has `roles/artifactregistry.writer` on the `meeting-briefing` repository, or build locally with `docker build` and `docker push` |

## Cost

What is billed, all to the billing account linked in step 2:

- **Agent Runtime**: vCPU and memory while the agent runs. With
  `agent_min_instances = 0` (the default here) it scales to zero between
  calls. Each instance gets `agent_cpu` / `agent_memory` (default 1 vCPU and
  2Gi; the runtime's own default is 4 vCPU and 4Gi). The first 50 vCPU-hours
  and 100 GiB-hours each month are free, counted per billing account, so
  other projects on the same billing account share them.
  Agent Runtime also bills session storage, but this agent keeps sessions in
  memory, so there is none.
- **Gemini on Vertex AI**: input and output tokens per briefing (none when
  there are no events), and the judge model when you run the evaluation
  (`tests/eval`: 3 writer calls and 3 judge calls per run).
- **Cloud Run**: request time of the MCP front; it scales to zero.
- **Cloud Build, Artifact Registry, Cloud Storage, Cloud Trace**: small
  amounts for builds, the image and the state bucket. The image repository
  deletes versions older than 7 days but always keeps the 3 newest.

Free tiers apply per billing account. Check the current prices on the
[Agent Platform pricing](https://cloud.google.com/products/gemini-enterprise-agent-platform/pricing),
[Vertex AI pricing](https://cloud.google.com/vertex-ai/pricing) and
[Cloud Run pricing](https://cloud.google.com/run/pricing) pages.

### Budget alert

Set a budget by hand (Terraform here has no access to the billing account's
budgets): **Billing → Budgets & alerts → Create budget**, scope it to this
project, and add email alerts, for example at 50%, 90% and 100%.

A budget only sends alerts; it does not stop spending. Only the accounts in
`invoker_members` can call the MCP front, and `agent_max_instances` caps how
many agent instances run at once. To stop spending, run the tear down below.

## Tear down

`infra/main` reads `dist/` even when destroying. In a fresh checkout, run
`scripts/build_agent_source.sh` first.

```bash
terraform -chdir=infra/main destroy
```

To delete the project too, set `deletion_policy = "DELETE"` in
`infra/bootstrap/terraform.tfvars` and apply. The state bucket keeps old
versions and refuses to be deleted while it holds any, so empty it:

```bash
gcloud storage rm --recursive --all-versions "gs://<project_id>-tfstate/**"
```

Then:

```bash
terraform -chdir=infra/bootstrap destroy
```

A deleted project can be restored for 30 days. Remove the domain-wide
delegation entry in the Admin console as well.
