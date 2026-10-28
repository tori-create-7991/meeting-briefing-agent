output "mcp_url" {
  description = "Register this URL in Claude Code (docs/deploy.md)."
  value       = "${google_cloud_run_v2_service.mcp_front.uri}/mcp"
}

output "agent_runtime_resource" {
  value = google_vertex_ai_reasoning_engine.agent.id
}

output "workspace_reader_client_id" {
  description = "Authorize this client ID for domain-wide delegation in the Workspace Admin console."
  value       = google_service_account.workspace_reader.unique_id
}

output "agent_principal" {
  description = "Principal granted signBlob on workspace-reader."
  value       = local.runtime_member
}

output "agent_effective_identity" {
  description = "Identity reported by Agent Runtime; compare with agent_principal after the first apply."
  value       = google_vertex_ai_reasoning_engine.agent.spec[0].effective_identity
}
