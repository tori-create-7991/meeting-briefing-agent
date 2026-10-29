resource "google_artifact_registry_repository" "images" {
  location      = var.region
  repository_id = "meeting-briefing"
  format        = "DOCKER"

  # Keep the free 0.5 GB from filling with old builds: delete versions older
  # than 7 days, except the 3 newest (KEEP wins over DELETE), so the image
  # Cloud Run serves and a rollback target always stay.
  cleanup_policy_dry_run = false
  cleanup_policies {
    id     = "delete-older-than-7d"
    action = "DELETE"
    condition {
      tag_state  = "ANY"
      older_than = "604800s"
    }
  }
  cleanup_policies {
    id     = "keep-3-newest"
    action = "KEEP"
    most_recent_versions {
      keep_count = 3
    }
  }

  depends_on = [google_project_service.main]
}
