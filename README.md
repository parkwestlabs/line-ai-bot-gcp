# Serverless LINE Bot V3 Template (FastAPI + Cloud Run)

LINE bot SDK Python V3 Async 版を GCP Cloud Run で動かす実運用向け LINE BOT テンプレートです。

## ✨ Overview

* 入り口に go を利用することで、コールドスタートしても高速レスポンスします (実測値: 121ms)
* メッセージ重複時はスルーします。(`--max-instances 1` 前提)
* FastAPIの `BackgroundTasks` を利用し、レスポンス後に裏側で非同期処理します。
* uv を使い、Pylance / Ruff の厳格な型チェック・静的解析を100%通過しています。

## 🚀 Quick Start (GCP Cloud Run)

### 0. GCP Project 作成

* GCP PROJECT を作成、必要な services enable します。
* 詳細は [docs/deploy-cli.md](docs/deploy-cli.md) 参照

```bash
# 例
PROJECT_ID=my-bot-20260628-test
PROJECT_NAME="LINE bot Project"

# project 作成
gcloud projects create $PROJECT_ID --name="${PROJECT_NAME}"
# default に設定する
gcloud config set project $PROJECT_ID

# Cloud Run に必要な service を有効化
gcloud services enable \
  artifactregistry.googleapis.com \
  cloudbuild.googleapis.com \
  run.googleapis.com \
  secretmanager.googleapis.com
```

### 1. Infra 構築

* 詳細は [docs/deploy-terraform.md](docs/deploy-terraform.md) 参照

```bash
cd terraform-gcp/

gcloud auth application-default login

# terraform.tfvars を作成・値を適宜修正する
cp terraform.tfvars.sample terraform.tfvars
```

* 初回の `terraform apply` では docker image がないため、ダミーイメージを指定する
* cloud_run.tf > template > containers > image を一時的に修正して apply する
* GitHub Actions による自動ビルドで registry 上に docker image ができたあとは本来の image に戻す

```terraform
    containers {
      # 🚀 初回構築時は、Artifact Registryが空なので以下のダミーイメージを指定して apply する
      image = "us-docker.pkg.dev/cloudrun/container/hello:latest"

      # (その後、GitHub Actionsが成功したら本来のURLに書き換えて、lifecycleで固定する)
      # image = "${var.region}-docker.pkg.dev/${var.project_id}/${var.gar_repo_name}/${local.service_name}:latest"
```

```bash
terraform plan
terraform apply
```

### 2. GCP のシークレットの登録

* `terraform apply` で作成された GCP 上の secret に手動で値を入れる

```bash
echo -n "your_secret" | gcloud secrets versions add LINE_CHANNEL_SECRET --data-file=-
echo -n "your_token" | gcloud secrets versions add LINE_CHANNEL_ACCESS_TOKEN --data-file=-
```

### 3. GitHub Actions による自動ビルド＆デプロイ

* main に push 後に自動で build & deploy される
* 事前に GitHub Secrets に必要な値を登録
* 詳細は [docs/deploy-gha.md](docs/deploy-gha.md) 参照

```bash
terraform output
# line_bot_url > LINE DevelopersのWebhook URLに登録する
# artifact_registry_repo_url > GitHub Secrets の GAR_REPO_URL に登録する
# github_actions_sa_email > GitHub Secrets の WIF_SERVICE_ACCOUNT に登録する
# workload_identity_provider > GitHub Secrets の WIF_PROVIDER に登録する

# 念のため、PROJECT_ID 表示
gcloud config get-value project

gh secret set PROJECT_ID --body $PROJECT_ID
gh secret set WIF_PROVIDER --body $WIF_PROVIDER
gh secret set WIF_SERVICE_ACCOUNT --body $WIF_SERVICE_ACCOUNT
gh secret set GAR_REPO_URL --body $GAR_REPO_URL
```

* Cloud Run 管理画面 > セキュリティ > 認証 > パブリックアクセスを確認・必要なら許可 (初回のみ)
* 発行された Service URL 末尾に `/webhook` をつけて LINE Developers に登録して、検証ボタンから接続を確認する
* 万が一 BackgroundTasks が完了しない場合は `--no-cpu-throttling` の追加を検討する

## 🛠️ Local Dev Notes

* Go Proxy: [./proxy/README.md](./proxy/README.md)
* Python Backend: [./backend/README.md](./backend/README.md)

## ⚖️ ライセンス
MIT License (ご自由にお使いください！)
