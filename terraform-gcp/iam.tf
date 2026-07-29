resource "google_service_account" "cloudrun_sa" {
  account_id   = "${local.service_name}-run-sa"
  display_name = "Cloud Run Execution Service Account for ${local.service_name}"
}

variable "cloudrun_sa_roles" {
  type = list(string)
  default = [
    "roles/storage.objectViewer",
    "roles/logging.logWriter",
    "roles/aiplatform.user",
  ]
}

resource "google_project_iam_member" "cloudrun_sa_bindings" {
  for_each = toset(var.cloudrun_sa_roles)

  project = var.project_id
  role    = each.value
  member  = "serviceAccount:${google_service_account.cloudrun_sa.email}"
}
