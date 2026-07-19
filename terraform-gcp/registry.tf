resource "google_artifact_registry_repository" "cloud_run_source_deploy" {
  project       = var.project_id
  location      = var.region
  repository_id = var.gar_repo_name
  description   = "Cloud Run Source Deployments"
  format        = "DOCKER"

  cleanup_policies {
    action = "KEEP"
    id     = "keep-latest-image"
    most_recent_versions {
      keep_count = 1
    }
  }

  cleanup_policies {
    action = "DELETE"
    id     = "delete-untagged-images"
    condition {
      older_than = "86400s"
      tag_state  = "UNTAGGED"
    }
  }
}
