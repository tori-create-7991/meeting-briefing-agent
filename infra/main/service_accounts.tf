# Signs domain-wide delegation JWTs for the agent. Holds no GCP roles; what it
# can read is decided only by the Workspace Admin console grant.
resource "google_service_account" "workspace_reader" {
  account_id   = "workspace-reader"
  display_name = "Workspace reader (domain-wide delegation, keyless)"
  depends_on   = [google_project_service.main]
}

# Runtime identity of the Cloud Run MCP front.
resource "google_service_account" "mcp_front" {
  account_id   = "mcp-front"
  display_name = "MCP front (Cloud Run)"
  depends_on   = [google_project_service.main]
}

# Fallback runtime identity for the agent when Agent Identity cannot be used.
resource "google_service_account" "briefing_runtime" {
  count        = var.runtime_identity == "service_account" ? 1 : 0
  account_id   = "briefing-runtime"
  display_name = "Briefing agent runtime (fallback)"
  depends_on   = [google_project_service.main]
}
