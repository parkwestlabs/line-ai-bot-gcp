# Python FastAPI Notes

## local サーバー起動

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

## アクセスのテスト

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
