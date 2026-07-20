output "line_bot_proxy_url" {
  description = "LINE DevelopersのWebhook URLに登録するCloud RunのURL"
  value       = google_cloud_run_v2_service.my_line_bot_proxy.uri
}

output "github_actions_sa_email" {
  description = "GitHub ActionsのCI/CD設定に使用するサービスアカウントのメールアドレス"
  value       = google_service_account.github_actions_deployer.email
}

output "workload_identity_provider" {
  description = "GitHub Actionsのauthステップで指定するWorkload Identityプロバイダーのフルパス"
  value       = google_iam_workload_identity_pool_provider.github_provider.name
}

output "artifact_registry_repo_url" {
  description = "GitHub ActionsやDocker Pushで使用するArtifact RegistryのリポジトリURL"
  value       = "${var.region}-docker.pkg.dev/${var.project_id}/${var.gar_repo_name}"
}
