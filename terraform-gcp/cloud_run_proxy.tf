# ==============================================================================
# Go Proxy 用 Cloud Run サービス
# ==============================================================================
resource "google_cloud_run_v2_service" "my_line_bot_proxy" {
  project              = var.project_id
  name                 = "${local.service_name}-proxy" # proxy用サービス名 (例: my-repo-proxy)
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
      # 🚀 初回 terraform apply 時は Artifact Registry にイメージがないため、
      # 下記のコメントアウトを一時的に外し、上の image 行をコメントアウトして apply してください。
      # image = "us-docker.pkg.dev/cloudrun/container/hello:latest"
      image = "${var.region}-docker.pkg.dev/${var.project_id}/${var.gar_repo_name}/${local.service_name}-proxy:latest"

      # Goプロキシに必要な環境変数
      env {
        name = "LINE_CHANNEL_SECRET"
        value_source {
          secret_key_ref {
            secret  = "LINE_CHANNEL_SECRET"
            version = "latest"
          }
        }
      }

      # Pythonバックエンドへの転送先URL
      # Python側Cloud RunのURLを指定（またはSecret経由）
      env {
        name  = "PYTHON_BACKEND_URL"
        value = "${google_cloud_run_v2_service.my_line_bot.uri}/webhook" # バックエンドのURLを自動連携！
      }

      ports {
        container_port = 8080
      }

      resources {
        cpu_idle = true
        limits = {
          cpu    = "1000m"
          memory = "256Mi" # Goは超軽量なため、256Miでも十分動作します（コスト削減）
        }
        startup_cpu_boost = true
      }
    }

    scaling {
      max_instance_count = 1
      min_instance_count = 0
    }
  }

  lifecycle {
    ignore_changes = [
      template[0].labels["commit-sha"],
      template[0].labels["goog-terraform-provisioned"],
    ]
  }
}
