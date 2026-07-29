variable "gcp_services" {
  type = list(string)
  default = [
    "artifactregistry.googleapis.com", # コンテナイメージ管理
    "cloudbuild.googleapis.com",
    "run.googleapis.com", # Cloud Run
    "secretmanager.googleapis.com",
  ]
}

resource "google_project_service" "enabled_services" {
  for_each = toset(var.gcp_services)

  project            = var.project_id
  service            = each.value
  disable_on_destroy = false # terraform destroy時にAPIが無効化されてデータが消えるのを防ぐ
}
