locals {
  secret_names = [
    "LINE_CHANNEL_SECRET",
    "LINE_CHANNEL_ACCESS_TOKEN"
  ]
}

resource "google_secret_manager_secret" "line_bot_secrets" {
  for_each = toset(local.secret_names)

  project   = var.project_id
  secret_id = each.value

  replication {
    auto {
    }
  }
}

resource "google_secret_manager_secret_iam_member" "line_bot_secret_accessors" {
  for_each = toset(local.secret_names)

  project   = var.project_id
  member    = "serviceAccount:${data.google_project.current.number}-compute@developer.gserviceaccount.com"
  secret_id = google_secret_manager_secret.line_bot_secrets[each.value].id
  role      = "roles/secretmanager.secretAccessor"
}
