# Cloud Build runs as this service account instead of the Compute Engine
# default one, which new projects create without any roles. It can only read
# and write the build bucket, push to the image repository and write logs.
resource "google_service_account" "mcp_builder" {
  account_id   = "mcp-builder"
  display_name = "Builds the MCP front image (Cloud Build)"
  depends_on   = [google_project_service.main]
}

# Holds uploaded build sources and build logs; both expire after 7 days.
resource "google_storage_bucket" "build" {
  name                        = "${var.project_id}-build"
  location                    = var.region
  uniform_bucket_level_access = true
  public_access_prevention    = "enforced"
  force_destroy               = true

  lifecycle_rule {
    condition {
      age = 7
    }
    action {
      type = "Delete"
    }
  }
}

resource "google_storage_bucket_iam_member" "builder_build_bucket" {
  bucket = google_storage_bucket.build.name
  role   = "roles/storage.objectAdmin"
  member = google_service_account.mcp_builder.member
}

# Cloud Build checks storage.buckets.get on the source and log bucket before
# it starts; objectAdmin does not include it.
resource "google_storage_bucket_iam_member" "builder_build_bucket_reader" {
  bucket = google_storage_bucket.build.name
  role   = "roles/storage.legacyBucketReader"
  member = google_service_account.mcp_builder.member
}

resource "google_artifact_registry_repository_iam_member" "builder_push" {
  location   = google_artifact_registry_repository.images.location
  repository = google_artifact_registry_repository.images.name
  role       = "roles/artifactregistry.writer"
  member     = google_service_account.mcp_builder.member
}

resource "google_project_iam_member" "builder_logs" {
  project = var.project_id
  role    = "roles/logging.logWriter"
  member  = google_service_account.mcp_builder.member
}
