# WIFのプール（大元の箱）
resource "google_iam_workload_identity_pool" "github_pool" {
  project                   = var.project_id
  display_name              = "GitHub Actions Pool"
  workload_identity_pool_id = "github-pool"
}

# WIFのプロバイダ（GitHubとの接続窓口）
resource "google_iam_workload_identity_pool_provider" "github_provider" {
  project                            = var.project_id
  display_name                       = "GitHub Actions Provider"
  workload_identity_pool_id          = var.wif_pool_name
  workload_identity_pool_provider_id = var.wif_provider_name
  attribute_condition                = "attribute.repository=='${var.github_repo_owner}/${var.github_repo_name}'"
  attribute_mapping = {
    "attribute.repository" = "assertion.repository"
    "google.subject"       = "assertion.sub"
  }
  oidc {
    issuer_uri = "https://token.actions.githubusercontent.com"
  }
}

# デプロイ専用のサービスアカウント本体
resource "google_service_account" "github_actions_deployer" {
  project      = var.project_id
  account_id   = var.wif_sa_name
  display_name = "GitHub Actions Deployer"
}

# GitHubとサービスアカウントを結ぶ最初の認証の鍵（ログイン許可）
resource "google_service_account_iam_member" "wif_user" {
  member             = "principalSet://iam.googleapis.com/projects/${data.google_project.current.number}/locations/global/workloadIdentityPools/${var.wif_pool_name}/attribute.repository/${var.github_repo_owner}/${var.github_repo_name}"
  service_account_id = "projects/${var.project_id}/serviceAccounts/${google_service_account.github_actions_deployer.email}"
  role               = "roles/iam.workloadIdentityUser"
}

# ログインした後に、Cloud Runのデプロイで他のSA（Computeデフォルト等）を身代わりに使うための鍵
resource "google_service_account_iam_member" "wif_sa_sa_user" {
  member             = "serviceAccount:${google_service_account.github_actions_deployer.email}"
  service_account_id = "projects/${var.project_id}/serviceAccounts/${data.google_project.current.number}-compute@developer.gserviceaccount.com"
  role               = "roles/iam.serviceAccountUser"
}

resource "google_project_iam_member" "wif_sa_ar_writer" {
  project = var.project_id
  member  = "serviceAccount:${google_service_account.github_actions_deployer.email}"
  role    = "roles/artifactregistry.writer"
}

resource "google_project_iam_member" "wif_sa_run_developer" {
  project = var.project_id
  member  = "serviceAccount:${google_service_account.github_actions_deployer.email}"
  role    = "roles/run.developer"
}
