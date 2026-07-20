# Go Notes & Local Testing

* cold start 高速化のため、LINE Webhook 受信用 go の proxy を作成した際の開発・テストのメモ
* **公式 SDK:** https://github.com/line/line-bot-sdk-go

---

## Init

```bash
mkdir proxy && cd proxy

# go.mod の作成
go mod init line-bot-proxy

# SDK のインストール (go.sum が作られる)
go get -u github.com/line/line-bot-sdk-go/v8/linebot

# 依存関係の整理（未使用のライブラリのお掃除）
go mod tidy
```

## Unit test

```bash
# ユニットテストの実行
go test -v

# テストカバレッジの確認
go test -cover
# coverage: 67.7% of statements
```

## サーバー単体起動テスト (ローカル)

```bash
# ダミーの環境変数で起動
LINE_CHANNEL_SECRET=dummy_secret LINE_CHANNEL_ACCESS_TOKEN=dummy_token go run main.go

# 署名なしリクエスト送信 -> invalid signature とログに出ればOK
curl -X POST http://localhost:8080/webhook
```

## Dockerfile 単体のテスト

* HMAC-SHA256 署名の生成

```bash
PAYLOAD='{"events":[{"type":"message","replyToken":"dummy_reply_token","message":{"type":"text","text":"Hello"}}]}'

# ダミー署名の生成
echo -n "${PAYLOAD}" | openssl dgst -sha256 -hmac 'dummy_secret' -binary | openssl enc -base64
```

* docker イメージを build してサーバーを起動する

```bash
docker build -t go-proxy .

docker run -p 8080:8080 \
  -e LINE_CHANNEL_SECRET=dummy_secret \
  -e PYTHON_BACKEND_URL=dummy_url \
  --name my-proxy --rm go-proxy

# 1. 不正な署名でリクエスト -> Webhook error: invalid signature と出る
curl -X POST http://localhost:8080/webhook \
  -H "Content-Type: application/json" \
  -H "X-Line-Signature: dummy_signature" \
  -d '{"events": [{"type": "message", "text": "hello"}]}'

# 2. 正しい計算値の署名でリクエスト -> 署名検証を通過し、転送エラーが出る
curl -X POST http://localhost:8080/webhook \
  -H "Content-Type: application/json" \
  -H "X-Line-Signature: +iJFAuywl3G/vK39Us4jTmlpfaLrnb7+iNxqBOnuyuA=" \
  -d "${PAYLOAD}"

# Failed to forward event to Python: Post "dummy_url": unsupported protocol scheme ""
```

## Docker Compose 統合テスト (Go + Python)

* ローカル環境で Go プロキシ ➔ Python バックエンドの連携動作を確認します。
* `compose.yaml` を local テストの便宜のため作成

```bash
docker compose up --build
```

```bash
# 1. テスト用のダミーペイロード準備
PAYLOAD='{
  "destination": "U12345678901234567890123456789012",
  "events": [
    {
      "type": "message",
      "message": {
        "type": "text",
        "id": "12345678901234",
        "text": "テスト送信",
        "quoteToken": "dummy_quote_token"
      },
      "timestamp": 1625097600000,
      "source": {
        "type": "user",
        "userId": "U12345678901234567890123456789012"
      },
      "replyToken": "dummy_reply_token",
      "mode": "active",
      "webhookEventId": "test-event-001",
      "deliveryContext": {
        "isRedelivery": false
      }
    }
  ]
}'

# 2. HMAC-SHA256 署名を計算 (LINE_CHANNEL_SECRET="dummy_secret_for_local_test")
SECRET="dummy_secret_for_local_test"
SIGNATURE=$(echo -n "$PAYLOAD" | openssl dgst -sha256 -hmac "$SECRET" -binary | base64)

# 3. リクエスト送信
curl -X POST http://localhost:8080/webhook \
  -H "Content-Type: application/json" \
  -H "X-Line-Signature: $SIGNATURE" \
  -d "$PAYLOAD"

# Go 経由で Python 側に到達し、LINE API への返信時に 401 エラーにる
# linebot.v3.messaging.exceptions.ApiException: (401)
# Reason: Unauthorized
```
