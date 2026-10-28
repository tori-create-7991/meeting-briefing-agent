resource "google_cloud_run_v2_service" "mcp_front" {
  name                = "mcp-front"
  location            = var.region
  ingress             = "INGRESS_TRAFFIC_ALL"
  deletion_protection = false

  template {
    service_account = google_service_account.mcp_front.email

    scaling {
      max_instance_count = 2
    }

    containers {
      image = var.mcp_image

      env {
        name  = "AGENT_RUNTIME_RESOURCE"
        value = google_vertex_ai_reasoning_engine.agent.id
      }
      env {
        name  = "GOOGLE_CLOUD_PROJECT"
        value = var.project_id
      }
      env {
        name  = "GOOGLE_CLOUD_LOCATION"
        value = var.region
      }
    }
  }

  depends_on = [google_project_service.main]
}

# Only the listed principals may call the service; Cloud Run rejects every
# other request before it reaches the app.
resource "google_cloud_run_v2_service_iam_member" "invokers" {
  for_each = toset(var.invoker_members)
  name     = google_cloud_run_v2_service.mcp_front.name
  location = var.region
  role     = "roles/run.invoker"
  member   = each.value
}
