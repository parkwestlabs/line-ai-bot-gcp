# ===================================================
# 1. ビルド用ステージ (Goのコンパイルを行う環境)
# ===================================================
FROM golang:1.26-alpine AS builder

# HTTPS通信（Cloud Runなどの本番環境）に必要なSSL証明書をインストール
RUN apk add --no-cache ca-certificates

WORKDIR /app

COPY . ./

# CGO_ENABLED=0 C言語依存をしない設定 (Alpine Linux での起動に必要)
# GOOS=linux Linux 向けにビルドすることを明示
# GOARCH=amd64 Cloud Run 環境では amd64 が標準 (指定しなければ自動)
# -ldflags="-w -s" バイナリからデバッグ情報を削りバイナリサイズを 30〜50% 超軽量化
RUN CGO_ENABLED=0 GOOS=linux go build -ldflags="-w -s" -o ./go-proxy .

# ===================================================
# 2. 実行用ステージ (本番環境用の超軽量環境)
# ===================================================
FROM scratch

WORKDIR /app

COPY --from=builder /etc/ssl/certs/ca-certificates.crt /etc/ssl/certs/
COPY --from=builder /app/go-proxy .

# 65534 (nobody ユーザー) の権限でアプリを実行する
USER 65534:65534

# Cloud Run等から注入されるPORT環境変数（デフォルト8080）で待機
EXPOSE 8080

# バイナリを直接実行
ENTRYPOINT ["./go-proxy"]
