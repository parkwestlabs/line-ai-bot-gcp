resource "google_cloud_run_v2_service" "my_line_bot" {
  project              = var.project_id
  name                 = local.service_name
  location             = var.region
  client               = "gcloud"
  client_version       = "568.0.0"
  invoker_iam_disabled = true
  scaling {
    min_instance_count = 0
  }
  template {
    labels = {
      managed-by = "github-actions"
    }
    service_account = "${data.google_project.current.number}-compute@developer.gserviceaccount.com"
    containers {
      # 🚀 初回構築時は、Artifact Registryが空なので以下のダミーイメージを指定して apply する
      # image = "us-docker.pkg.dev/cloudrun/container/hello:latest"
      image = "${var.region}-docker.pkg.dev/${var.project_id}/${var.gar_repo_name}/${local.service_name}:latest"

      env {
        name = "LINE_CHANNEL_ACCESS_TOKEN"
        value_source {
          secret_key_ref {
            secret  = "LINE_CHANNEL_ACCESS_TOKEN"
            version = "latest"
          }
        }
      }
      env {
        name = "LINE_CHANNEL_SECRET"
        value_source {
          secret_key_ref {
            secret  = "LINE_CHANNEL_SECRET"
            version = "latest"
          }
        }
      }
      ports {
        container_port = 8080
      }
      resources {
        cpu_idle = true
        limits = {
          cpu    = "1000m"
          memory = "512Mi"
        }
        startup_cpu_boost = true
      }
    }
    scaling {
      max_instance_count = 1
      min_instance_count = 0
    }
  }

  # GitHub Actions からのデプロイと Terraform を共存させるために、
  # commit-sha の変更を「Terraformの監視対象から外す（無視する）」という設定
  lifecycle {
    ignore_changes = [
      template[0].labels["commit-sha"],
      template[0].labels["goog-terraform-provisioned"],
    ]
  }
}
