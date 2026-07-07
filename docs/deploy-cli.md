# Deploy with gcloud CLI

* `gcloud` による Cloud Run への deploy 試行錯誤の記録
* 公式doc: https://docs.cloud.google.com/run/docs/quickstarts/build-and-deploy/deploy-python-fastapi-service?hl=ja

```bash
# https://docs.cloud.google.com/sdk/docs/downloads-homebrew?hl=ja
brew update && brew install --cask gcloud-cli
gcloud components update

gcloud --version
# Google Cloud SDK 574.0.0
```

## Login

```bash
# 最初に auth login と config set project を
# 対話形式でまとめてできる初期コマンド
gcloud init
```

```bash
# ログインする
gcloud auth login

# ACTIVE 列の * がデフォルトのアカウント
gcloud auth list

# 選択中のアカウントを表示する
gcloud config get-value account

# 設定のまとめ表示
gcloud config configurations list
gcloud config list
```

## Project

__(注) PROJECT_ID について__

* 世界中で重複していないユニークな名前である必要があります
* PROJECT_ID には30文字の長さ制限があります
* 「完全な機密（シークレット）」ではありません。
* ただし、「むやみに外部に公開しない方が安全な情報（公開を推奨されない情報）」とのことです。
* 推奨: [組織名/社名]-[システム名]-[ランダム文字列や日付]-[環境名]
    * 例: my-app-20260628-dev (個人名は入れない)

```bash
PROJECT_ID=my-bot-20260628-test
# PROJECT_NAME は重複していても問題ないので、自由に名前を付けられる
PROJECT_NAME="LINE bot Project"

# プロジェクト作成
gcloud projects create $PROJECT_ID --name="${PROJECT_NAME}"

# default に設定する
gcloud config set project $PROJECT_ID

# project の一覧を確認する
gcloud projects list

# 選択中の PROJECT_ID を表示する
gcloud config get-value project

# 番号も付与される
PROJECT_NUMBER=$(gcloud projects describe $PROJECT_ID --format='value(projectNumber)')
```

```bash
# BILLING_ACCOUNT_ID を表示する
gcloud billing accounts list

BILLING_ACCOUNT_ID="0X0X0X-0X0X0X-0X0X0X"

gcloud billing projects link $PROJECT_ID --billing-account=$BILLING_ACCOUNT_ID

gcloud billing projects list --billing-account=$BILLING_ACCOUNT_ID
```

```bash
gcloud services list --enabled

# Cloud Run に必要な service を有効化
gcloud services enable \
  artifactregistry.googleapis.com \
  cloudbuild.googleapis.com \
  run.googleapis.com
```

一旦 `.env` を作り、LINE Developers から2つの変数をコピーする

```
LINE_CHANNEL_SECRET=your_secret_here
LINE_CHANNEL_ACCESS_TOKEN=your_token_here
```

## Build and Deploy

```bash
# 任意の名前でOK
SERVICE_NAME=my-line-bot

# us-central1 は一定の無料枠（リクエスト数やCPU時間）の範囲内であれば無料とのこと
REGION=us-central1

# default region も設定できる
gcloud config set run/region $REGION

# 確認
gcloud config list

# local の source を直接 deploy するコマンド
# gcloud run deploy $SERVICE_NAME \
#   --source . \
#   --region $REGION \
#   --allow-unauthenticated \
#   --cpu-boost \
#   --max-instances 1 \
#   --env-vars-file=.env

# A repository named [cloud-run-source-deploy] in region [us-central1] will be created.
# Do you want to continue (Y/n)? Y

# gcloud run deploy --source . では GCP 上に DOCKER_BUILDKIT=1 を渡せないのでエラーになる
# (GCP上のエラー) the --mount option requires BuildKit.
# 代わりに、local で docker build して、docker image を push する

# repository 一覧
gcloud artifacts repositories list --location=$REGION

# (参考) repository を手動で作る場合、以下で自動作成と同等になる
gcloud artifacts repositories create cloud-run-source-deploy \
    --repository-format=docker \
    --location=$REGION \
    --description="Cloud Run Source Deployments"

# Dockerの認証設定
gcloud auth configure-docker ${REGION}-docker.pkg.dev --quiet

# local で docker build と push
REPO_URL="${REGION}-docker.pkg.dev/${PROJECT_ID}/cloud-run-source-deploy"
IMAGE_TAG="${REPO_URL}/${SERVICE_NAME}:latest"

# Mac ではデフォルトで docker buildx build が使われる
# Apple Silicon の場合 ARM64 ができるので linux/amd64 を指定する
docker build --platform linux/amd64 -t $IMAGE_TAG . --push

gcloud run deploy $SERVICE_NAME \
  --image $IMAGE_TAG \
  --region $REGION \
  --allow-unauthenticated \
  --cpu-boost \
  --max-instances 1 \
  --env-vars-file=.env

# deploy 結果の確認
gcloud run revisions list --service=$SERVICE_NAME
```

## Testing

```bash
# Cloud Run デプロイ後 URL が表示される。以下のURLであるはず。
SERVICE_URL="https://${SERVICE_NAME}-${PROJECT_NUMBER}.${REGION}.run.app"

# (参考) これは旧形式 URL を表示する
gcloud run services describe $SERVICE_NAME --region=$REGION \
  --format='value(status.url)'

# gcloudの認証トークンをヘッダーに載せて、公開されていない URL にアクセスする
curl -X POST \
  -H "Authorization: Bearer $(gcloud auth print-identity-token)" \
  $SERVICE_URL

# 公開するための allUsers への権限設定
gcloud beta run services add-iam-policy-binding --region=$REGION \
  --member=allUsers \
  --role=roles/run.invoker $SERVICE_NAME

# GCPの初期設定（特に一般アカウントや組織配下）で「ドメイン外のユーザー
# （allUsers＝インターネットの全員）への権限付与を禁止する組織ポリシー
# （constraints/iam.allowedPolicyMemberDomains）」がデフォルトで
# 有効化されている場合に以下のエラーになる

# ERROR: (gcloud.beta.run.services.add-iam-policy-binding) FAILED_PRECONDITION: One or more users named in the policy do not belong to a permitted customer,  perhaps due to an organization policy.
```

* 権限設定が上記のエラーで fail する場合、コンソールから手動で設定する
    * Cloud Run > Service名 > セキュリティ > 認証 > 公開アクセスを許可する

## Troubleshooting

```bash
# Error 403: PROJECT_NUMBER-compute@developer.gserviceaccount.com does not have storage.objects.get access to the Google Cloud Storage object.
# Permission 'storage.objects.get' denied on resource ...
# が出た場合は権限追加する
gcloud projects add-iam-policy-binding $PROJECT_ID \
    --member="serviceAccount:${PROJECT_NUMBER}-compute@developer.gserviceaccount.com" \
    --role="roles/storage.objectViewer"

# これも必要
gcloud projects add-iam-policy-binding $PROJECT_ID \
    --member="serviceAccount:${PROJECT_NUMBER}-compute@developer.gserviceaccount.com" \
    --role="roles/logging.logWriter"

# 権限の一覧
gcloud projects get-iam-policy $PROJECT_ID
```

```bash
# 自分の権限も追加
gcloud projects add-iam-policy-binding $PROJECT_ID \
    --member="user:$(gcloud config get-value account)" \
    --role="roles/logging.viewer"
```

## Logs

```bash
# source から deploy した場合の build ログ (image から deploy の場合は空っぽ)
gcloud builds log $(gcloud builds list --limit=1 --format="value(id)") | tail -n 20

# cloud run ログを console 上と似た感じでログを表示する
# --order=asc にはいろいろ問題があるので、Mac では tail -r で逆順にする
gcloud logging read "resource.type=cloud_run_revision AND resource.labels.service_name=$SERVICE_NAME" \
  --format="value(timestamp.date(tz=LOCAL), severity, jsonPayload.message)" \
   --limit=10 | tail -r

# tail -f 的なやつ (新規ログのみ表示する。直前のログをついでに出すことはできない)
gcloud beta run services logs tail $SERVICE_NAME
# Would you like to install the `log-streaming` component to continue command execution?
# と聞かれたら install する
```

## Secret Manager

* 実運用では `.env` の代わりに Secret Manager 経由で Cloud Run の環境変数を設定する

```bash
gcloud services list --enabled

gcloud services enable secretmanager.googleapis.com
```

* `LINE_CHANNEL_SECRET` と `LINE_CHANNEL_ACCESS_TOKEN` をそれぞれ作成する

```bash
SECRET_NAME="LINE_CHANNEL_SECRET"   # LINE_CHANNEL_ACCESS_TOKEN も

gcloud secrets create $SECRET_NAME --replication-policy="automatic"
echo -n "your_secret_here" | gcloud secrets versions add $SECRET_NAME --data-file=-

# 一覧
gcloud secrets list
gcloud secrets versions list $SECRET_NAME

# 表示
gcloud secrets versions access latest --secret=$SECRET_NAME

# 削除
gcloud secrets versions destroy バージョン番号 --secret=$SECRET_NAME
gcloud secrets delete $SECRET_NAME
```

```bash
# 通常は環境変数名とシークレット名は一致させる
# (例外はシークレット名の末尾に _PROD _DEV を付けて分けたい場合)
VAR1=LINE_CHANNEL_SECRET
VAR2=LINE_CHANNEL_ACCESS_TOKEN

gcloud run deploy $SERVICE_NAME \
  --image $IMAGE_TAG \
  --region $REGION \
  --allow-unauthenticated \
  --cpu-boost \
  --max-instances 1 \
  --update-secrets=${VAR1}=${VAR1}:latest,${VAR2}=${VAR2}:latest

# なお、--set-secrets は全体を上書きするため、指定していない環境変数は削除される
```

### ⚠️ 注意（トラブルシューティング）

* 最初に `--env-vars-file=.env` で deploy 後に `--update-secrets` に切り替えようとすると以下のエラーが発生する。
* GCPコンソール（画面）から一度環境変数を消すと deploy できるようになる。
    * 新しいリビジョンの編集とデプロイ > 変数とシークレット > ゴミ箱マークで削除 > デプロイ

> ERROR: (gcloud.run.deploy) Cannot update environment variable [LINE_CHANNEL_SECRET] to the given type because it has already been set with a different type.

* 以下のエラーが出たら権限を追加

> Permission denied on secret: projects/PROJECT_NUMBER/secrets/LINE_CHANNEL_SECRET/versions/latest for Revision service account PROJECT_NUMBER-compute@developer.gserviceaccount.com.
> The service account used must be granted the 'Secret Manager Secret Accessor' role (roles/secretmanager.secretAccessor) at the secret, project or higher level.

```bash
gcloud secrets add-iam-policy-binding $SECRET_NAME \
    --member="serviceAccount:${PROJECT_NUMBER}-compute@developer.gserviceaccount.com" \
    --role="roles/secretmanager.secretAccessor"
```

## Clean Up

```bash
gcloud run services delete $SERVICE_NAME --region $REGION

gcloud projects delete $PROJECT_ID
```
