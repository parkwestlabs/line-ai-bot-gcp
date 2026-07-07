# Serverless LINE Bot V3 Template (FastAPI + Cloud Run)

LINE bot SDK Python V3 Async 版を GCP Cloud Run で動かす実運用向け LINE BOT テンプレートです。

## ✨ Overview

* たまのリクエストでコールドスタートしても、なる早のレスポンスを目指します
* メッセージ重複時はスルーします。(`--max-instances 1` 前提)
* FastAPIの `BackgroundTasks` を利用し、レスポンス後に裏側で非同期処理します。
* uv を使い、Pylance / Ruff の厳格な型チェック・静的解析を100%通過しています。

## 🚀 Quick Start (GCP Cloud Run)

* GCP PROJECT 作成済みの前提で、以下のコマンドを実行します。
    * 詳細は [docs/deploy-cli.md](docs/deploy-cli.md) 参照

### 1. シークレットの作成・登録

```bash
gcloud secrets create LINE_CHANNEL_SECRET --replication-policy="automatic"
gcloud secrets create LINE_CHANNEL_ACCESS_TOKEN --replication-policy="automatic"

echo -n "your_secret" | gcloud secrets versions add LINE_CHANNEL_SECRET --data-file=-
echo -n "your_token" | gcloud secrets versions add LINE_CHANNEL_ACCESS_TOKEN --data-file=-
```

### 2. ビルド＆デプロイ

```bash
REGION=us-central1
PROJECT_ID=your-bot-project
SERVICE_NAME=your-line-bot-name-here

REPO_URL="${REGION}-docker.pkg.dev/${PROJECT_ID}/cloud-run-source-deploy"
IMAGE_TAG="${REPO_URL}/${SERVICE_NAME}:latest"

SECRET=LINE_CHANNEL_SECRET
TOKEN=LINE_CHANNEL_ACCESS_TOKEN

docker build --platform linux/amd64 -t $IMAGE_TAG . --push

gcloud run deploy $SERVICE_NAME --image $IMAGE_TAG --region $REGION \
  --allow-unauthenticated --cpu-boost --cpu=1 --memory=512Mi \
  --min-instances 0 --max-instances 1 \
  --update-secrets=${SECRET}=${SECRET}:latest,${TOKEN}=${TOKEN}:latest

# Service URL: https://SERVICE_NAME-PROJECT_NUMBER.REGION.run.app
```

* 発行された Service URL 末尾に `/webhook` をつけて LINE Developers に登録する
* 万が一 BackgroundTasks が完了しない場合は `--no-cpu-throttling` の追加を検討する

## 🛠️ Local Dev

### サーバー起動

* local server で外部からのアクセスを受けれるように設定も可能
* とはいえ、GCP に deploy してしまう方が簡単な気がします。

```bash
uv sync

uv run fastapi dev src/main.py

# または

docker build -t my-bot-app .
# local 開発デフォルトポートは 8000 だが、コンテナ内では 8080 で起動する
docker run --rm -p 8000:8080 --env-file .env.example my-bot-app
```

### アクセスのテスト

```bash
# X-Line-Signature 無しでリクエスト
curl -X POST http://localhost:8000/webhook
# {"detail":[{"type":"missing","loc":["header","x-line-signature"],"msg":"Field required","input":null}]}

# 署名検証の動作チェック
curl -X POST http://127.0.0.1:8000/webhook \
  -H "Content-Type: application/json" \
  -H "X-Line-Signature: dummy" \
  -d '{
    "events": [
      {
        "type": "message",
        "replyToken": "dummy_reply_token",
        "message": {
          "type": "text",
          "id": "12345",
          "text": "こんにちは！"
        }
      }
    ]
  }'
# {"detail":"Invalid Signature"}
```

## 📦 Init Project Notes

```bash
uv init --app .

uv add "fastapi[standard]" line-bot-sdk python-dotenv
uv add --dev ruff pyright pytest pytest-mock pytest-asyncio pytest-cov

mkdir src tests
```

## 👷 Upgrade Packages

```bash
uv pip list --outdated

uv sync --upgrade --dry-run
uv sync --upgrade
```

## ⚖️ ライセンス
MIT License (ご自由にお使いください！)
