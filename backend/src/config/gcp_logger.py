import json
import logging
import os

# Python の標準ログ属性（extraから除外するもの）
# クラスの外に定義して1カ所にまとめます
RESERVED_ATTRS = {
    "args",
    "asctime",
    "created",
    "exc_info",
    "exc_text",
    "filename",
    "funcName",
    "levelname",
    "levelno",
    "lineno",
    "module",
    "msecs",
    "message",
    "msg",
    "name",
    "pathname",
    "process",
    "processName",
    "relativeCreated",
    "stack_info",
    "thread",
    "threadName",
    "taskName",
}


def _extract_extra_data(record: logging.LogRecord) -> dict:
    """
    LogRecordからPython標準のログ属性を除外してユーザーが指定したextraのキーのみを抽出
    """
    return {
        key: value
        for key, value in record.__dict__.items()
        if key not in RESERVED_ATTRS
    }


class CloudRunJsonFormatter(logging.Formatter):
    """Cloud Run（Cloud Logging）に最適化したミニマルなJSONフォーマッタ"""

    def format(self, record: logging.LogRecord) -> str:
        # 1. 必須の基本フィールド（Cloud Runが認識する構造）に変換
        log_data = {
            "severity": record.levelname,
            "message": record.getMessage(),
            "time": self.formatTime(record, self.datefmt),
            "logging.googleapis.com/sourceLocation": {
                "file": record.filename,
                "line": str(record.lineno),
                "function": record.funcName,
            },
        }

        # 2. extra={} で渡されたカスタムデータをJSONのルートに展開
        log_data.update(_extract_extra_data(record))

        # 3. 例外（スタックトレース）がある場合は文字列として追加
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)

        return json.dumps(log_data, ensure_ascii=False)


class LocalTextFormatter(logging.Formatter):
    """ローカル開発環境用：人間が見やすく、extraの中身も末尾に表示するテキストフォーマッタ"""

    def format(self, record: logging.LogRecord) -> str:
        # 基本のテキスト形式を生成（例: [2026-06-30 18:45:00] [INFO] メッセージ）
        log_message = super().format(record)

        # extraで渡されたカスタムデータを抽出する
        extra_data = _extract_extra_data(record)

        # extraデータが存在する場合のみ、ログの末尾に綺麗に追加する
        if extra_data:
            log_message = f"{log_message}  [extra: {extra_data}]"

        return log_message


def setup_logging() -> None:
    """環境変数（K_SERVICE）に応じてフォーマットを自動切り替えする初期化関数"""
    log_level_name = os.getenv("LOG_LEVEL", "INFO").upper()
    log_level = getattr(logging, log_level_name, logging.INFO)

    # 1. ルートロガーの初期化
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)

    # 既存ハンドラのクリア（ハンドラの重複防止）
    for h in root_logger.handlers:
        root_logger.removeHandler(h)

    handler = logging.StreamHandler()

    if os.getenv("K_SERVICE"):
        # Cloud Run 環境
        handler.setFormatter(CloudRunJsonFormatter())
    else:
        # ローカル環境：人間が見やすい色なしのシンプルテキスト形式
        handler.setFormatter(
            LocalTextFormatter(
                "[%(asctime)s] [%(levelname)s] %(message)s",
                datefmt="%Y-%m-%d %H:%M:%S",
            )
        )

    root_logger.addHandler(handler)

    # 2. FastAPI/Uvicornのログもルートロガーに伝播させてフォーマットを統一する
    # さもないとUvicornだけtextPayload扱いでログレベルが判別不能(DEFAULT)になる
    for logger_name in ("uvicorn", "uvicorn.access", "uvicorn.error"):
        uvicorn_logger = logging.getLogger(logger_name)
        uvicorn_logger.handlers = []  # Uvicorn独自のハンドラを削除
        uvicorn_logger.propagate = True  # 親のルートロガーに処理を任せる


# root logger のメソッドを明示的に変数としてエクスポートする
# これにより、Ruffの「暗黙的なルートロガーの使用（LOG015）」の警告を完全に回避できます
_root_logger = logging.getLogger()

info = _root_logger.info
warning = _root_logger.warning
error = _root_logger.error
debug = _root_logger.debug
exception = _root_logger.exception
