# syntax=docker/dockerfile:1
FROM ghcr.io/astral-sh/uv:python3.14-trixie-slim AS builder

WORKDIR /app

# 💡 高速化のための最適化設定
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy

COPY pyproject.toml uv.lock ./

# 仮想環境（.venv）を作成し、依存関係を同期（インストール）
# --no-install-project をつけることで、ソースコードがなくても依存ライブラリだけ先にビルド
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-install-project --no-dev


FROM python:3.14-slim-trixie AS runner

WORKDIR /app

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONPATH="/app/src" \
    PATH="/app/.venv/bin:$PATH"

RUN groupadd -g 10001 appuser && \
    useradd -u 10001 -g appuser -m -s /sbin/nologin appuser

COPY --from=builder --chown=appuser:appuser /app/.venv /app/.venv
COPY --chown=appuser:appuser src ./src

USER appuser

EXPOSE 8080

# ここでは、インメモリの cache 利用のため、ワーカー数は明示的に1に絞る

# fastapi run により 0.0.0.0 で起動し、CPUコア数に合わせて自動でworker数が最適化される
# この場合 workder 数は 1 なので fastapi run のメリットはない
# CMD ["fastapi", "run", "src/main.py", "--port", "8080", "--workers", "1"]

# fastapi run よりも uvicorn 直接実行の方が起動が速い説がある
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080", "--workers", "1"]
