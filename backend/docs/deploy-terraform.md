# Deploy with terraform

* Cloud Run への deploy を Terraform で自動化・スクリプト化する

## Init

```bash
cd terraform-gcp/

# 最初の一回だけ初期化
terraform init
# Terraform has been successfully initialized!
# .terraform/ が作成される

gcloud auth application-default login
```

* ブラウザが開き、以下が出てくるので、チェックして続ける
    1. Google Cloud のデータの参照、編集、設定、削除、Google アカウントのメールアドレスの参照
    2. Google Cloud SQL インスタンスを参照してログインする (注: SQL使う場合にチェックすればいいらしい)
* `~/.config/gcloud/application_default_credentials.json` が作成され、自動で利用される
    * その結果、`provider "google"` に `credentials` や `access_token` は不要

## imports.tf 作成

* gcloud CLI で作成済みの infra を terraform 管理下にする方法
* 一時的なファイルとして `imports.tf` を用意する

```terraform
# imports.tf
import {
  to = <Terraform内でのリソース名>.＜任意の名前＞
  id = <クラウド側（GCPなど）の識別子>
}

# 例
import {
  to = google_artifact_registry_repository.app
  id = "projects/${var.project_id}/locations/${var.region}/repositories/${var.gar_repo_name}"
}
```

* プロンプト例

```
GCPにgcloud CLIでデプロイ済みのCloud Runアプリをterraformの管理下に移したいです。
gcloud CLIでの操作内容を以下に貼ります。
"terraform plan -generate-config-out=generated.tf"を実行するための、
いわゆるimports.tfを作りたいです。importブロックの内容を作成してください。
また、その前提として variables.tf に適宜変数を定義して再利用可能にしてください。

(ここに gcloud CLIでの操作内容を貼る)
```

* `imports.tf` に入れるのはユーザー管理のもののみを対象にする
    * 例: `google_service_account` は import する
    * `SA_NAME@PROJECT_ID.iam.gserviceaccount.com` は管理対象
* Google管理 や デフォルト自動作成のサービスアカウントは管理対象外
    * 例: `google_compute_default_service_account` は import しない
    * `PROJECT_NUMBER-compute@developer.gserviceaccount.com` は対象外
* デフォルトアカウント自体の管理はGCPに任せ、IAMポリシーの部分だけを管理対象にする
    * データソース (data) で参照できる

```terraform
# GCPが自動作成した「Compute Engineデフォルトサービスアカウント」の情報を読み込む
data "google_compute_default_service_account" "default" {
  project = var.project_id
}

# これで、コード内では以下のように「変数」として使い回せます！
# data.google_compute_default_service_account.default.email

# シークレットへの権限付与リソース（本体は作らないが、権限はTerraformが握る）
resource "google_secret_manager_secret_iam_member" "secret_accessor" {
  for_each  = var.secret_names
  project   = var.project_id
  secret_id = google_secret_manager_secret.secrets[each.key].secret_id
  role      = "roles/secretmanager.secretAccessor"

  # ベタ書きをせず、データソースから自動的にメールアドレスを補完する！
  member    = "serviceAccount:${data.google_compute_default_service_account.default.email}"
}
```

## imports.tf 実行

```bash
# imports.tf から generated.tf を生成
terraform plan -generate-config-out=generated.tf

# 万が一エラーになった場合
# gcloud の get 系コマンドで実際の値とのズレを確認して imports.tf を修正
# generated.tf を削除して generate-config-out を再実行

terraform plan
# Plan: 13 to import, 0 to add, 0 to change, 0 to destroy. などと出れば成功

# 一旦、内容を確定して terraform.tfstate を生成し terraform の管理下に入れる
terraform apply
# Apply complete! Resources: 13 imported, 0 added, 0 changed, 0 destroyed.

# terraform.tfstate` は一旦 local 管理として .gitignore に入れる
# local ではなくリモートバックエンド (GCSバケット) の利用が望ましい

# 再度実行して No changes. と出ることを確認
terraform plan
# No changes. Your infrastructure matches the configuration.

# generated.tf の中を変数に置き換えて、適宜ファイルに分割して整理整頓後、以下を繰り返す
terraform plan
terraform apply
```

* 整理整頓後、imports.tf と空になった generated.tf は削除可
* 参考として、imports.tf は imports.txt と rename して残している

## 整理整頓の例

### Before

* `LINE_CHANNEL_SECRET` と `LINE_CHANNEL_ACCESS_TOKEN` で重複している

```terraform
resource "google_secret_manager_secret" "line_channel_secret" {
  project   = var.project_id
  secret_id = "LINE_CHANNEL_SECRET"
  replication {
    auto {
    }
  }
}

resource "google_secret_manager_secret" "line_channel_access_token" {
  project   = var.project_id
  secret_id = "LINE_CHANNEL_ACCESS_TOKEN"
  replication {
    auto {
    }
  }
}
```

### Move

* locals で配列を定義して、変数を rename する指示を入れて `terraform plan` する
* `... has moved to google_secret_manager_secret.line_bot_secrets["LINE_CHANNEL_ACCESS_TOKEN"]` 等と出れば成功

```terraform
locals {
  secret_names = [
    "LINE_CHANNEL_SECRET",
    "LINE_CHANNEL_ACCESS_TOKEN"
  ]
}

# 🚀 既存のインポート済みデータを for_each の中に引っ越しさせる指示
moved {
  from = google_secret_manager_secret.line_channel_secret
  to   = google_secret_manager_secret.line_bot_secrets["LINE_CHANNEL_SECRET"]
}

moved {
  from = google_secret_manager_secret.line_channel_access_token
  to   = google_secret_manager_secret.line_bot_secrets["LINE_CHANNEL_ACCESS_TOKEN"]
}
```

* `terraform apply` で rename を確定する
* `moved` は削除する

### After

* DRY になった

```terraform
resource "google_secret_manager_secret" "line_bot_secrets" {
  for_each  = toset(local.secret_names)

  project   = var.project_id
  secret_id = each.value

  replication {
    auto {
    }
  }
}
```

## その他のコマンド

```bash
# outputs.tf の内容を表示する
terraform output

# format
terraform fmt

# validate the configuration
terraform validate

# inspect state
terraform show
```
