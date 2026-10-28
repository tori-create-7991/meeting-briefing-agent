# The agent signs delegation JWTs as workspace-reader. google.auth.iam.Signer
# calls the IAM Credentials signBlob API, so signBlob is the only permission,
# granted on that one service account only.
resource "google_project_iam_custom_role" "sign_blob" {
  role_id     = "briefingSignBlob"
  title       = "Briefing agent: sign as workspace-reader"
  permissions = ["iam.serviceAccounts.signBlob"]
}

resource "google_service_account_iam_member" "runtime_sign_blob" {
  service_account_id = google_service_account.workspace_reader.name
  role               = google_project_iam_custom_role.sign_blob.id
  member             = local.runtime_member
}

# Agent Identity already has inference access through its default roles. The
# fallback service account needs it granted.
resource "google_project_iam_member" "runtime_aiplatform_user" {
  count   = var.runtime_identity == "service_account" ? 1 : 0
  project = var.project_id
  role    = "roles/aiplatform.user"
  member  = local.runtime_member
}

# The MCP front may only look up and query the agent.
resource "google_project_iam_custom_role" "query_agent" {
  role_id = "briefingQueryAgent"
  title   = "Briefing MCP front: query the agent"
  permissions = [
    "aiplatform.reasoningEngines.get",
    "aiplatform.reasoningEngines.query",
  ]
}

resource "google_project_iam_member" "mcp_front_query_agent" {
  project = var.project_id
  role    = google_project_iam_custom_role.query_agent.id
  member  = "serviceAccount:${google_service_account.mcp_front.email}"
}
