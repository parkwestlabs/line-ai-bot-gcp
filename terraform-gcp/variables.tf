variable "project_id" {
  type        = string
  description = "GCPのプロジェクトID"
}

variable "region" {
  type        = string
  description = "デプロイ先のリージョン"
  default     = "us-central1"
}

variable "gar_repo_name" {
  type        = string
  description = "Google Artifact Registryのリポジトリ名"
  default     = "cloud-run-source-deploy"
}

# ====================================================================
# GitHub Actions / Workload Identity Federation 関連の変数
# ====================================================================

variable "github_repo_owner" {
  type        = string
  description = "GitHubのユーザー名、またはオーガニゼーション名"
}

variable "github_repo_name" {
  type        = string
  description = "GitHubのリポジトリ名"
}

variable "wif_pool_name" {
  type        = string
  description = "Workload Identity Pool名"
  default     = "github-pool"
}

variable "wif_provider_name" {
  type        = string
  description = "Workload Identity Provider名"
  default     = "github-provider"
}

variable "wif_sa_name" {
  type        = string
  description = "GitHub Actions デプロイ専用サービスアカウント名"
  default     = "github-actions-deployer"
}

# ====================================================================
# local 変数 / データソース
# ====================================================================

locals {
  # Cloud Runのサービス名
  # 連動させる便宜上、github_repo_name は小文字の英数字とハイフンのみ使用する
  service_name = var.github_repo_name
}

# 現在のプロジェクトの情報をGCPから読み込むデータソース
data "google_project" "current" {
  project_id = var.project_id
}
