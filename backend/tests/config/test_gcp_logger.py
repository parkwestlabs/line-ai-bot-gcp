import json
import logging
import os
from unittest.mock import patch

import pytest

# logger.py から設定関数や関数をインポート（環境に合わせてパスを変更してください）
from config.gcp_logger import _extract_extra_data, setup_logging


@pytest.fixture(autouse=True)
def reset_logging():
    """テストごとにロガーの状態を完全にリセットするフィクスチャ"""
    root_logger = logging.getLogger()
    # 既存のハンドラをすべて削除
    for h in list(root_logger.handlers):
        root_logger.removeHandler(h)
    yield
    # テスト後にも綺麗にする
    for h in list(root_logger.handlers):
        root_logger.removeHandler(h)


def test_extract_extra_data():
    """_extract_extra_data が標準属性を除外して extra のみを取り出せるかテスト"""
    record = logging.LogRecord(
        name="test",
        level=logging.INFO,
        pathname="test.py",
        lineno=10,
        msg="Hello",
        args=(),
        exc_info=None,
    )

    # テスト実行環境の標準属性（taskName等を含む）をキャプチャしておく
    default_keys = set(record.__dict__.keys())

    # ユーザーが任意に追加したデータをシミュレート
    record.__dict__["user_id"] = 12345
    record.__dict__["request_path"] = "/items"

    extra = _extract_extra_data(record)

    assert extra == {"user_id": 12345, "request_path": "/items"}
    assert "levelname" not in extra  # 標準属性は入っていないこと

    # 環境に依存する標準キー（taskNameやlevelnameなど）が混入していないか検証
    for key in default_keys:
        assert key not in extra


def test_local_logging_format(capsys: pytest.CaptureFixture[str]):
    """ローカル環境（K_SERVICEなし）で人間向けのテキスト形式で出力されるかテスト"""
    with patch.dict(os.environ, {}, clear=True):
        setup_logging()
        logger = logging.getLogger()

        # extra付きでログを出力
        logger.info("ローカルテストです", extra={"debug_info": "secret"})

        # 標準出力をキャプチャ
        captured = capsys.readouterr()

        assert (
            "ローカルテストです" in captured.err
        )  # StreamHandlerはデフォルトでstderrに出力します
        assert "[INFO]" in captured.err
        assert "[extra: {'debug_info': 'secret'}]" in captured.err


def test_cloud_run_logging_format(capsys: pytest.CaptureFixture[str]):
    """Cloud Run環境（K_SERVICEあり）で正しいGCP向けJSON形式で出力されるかテスト"""
    # 環境変数を擬似的に設定
    with patch.dict(os.environ, {"K_SERVICE": "my-test-service"}):
        setup_logging()
        logger = logging.getLogger()

        logger.info("本番テストです", extra={"user_id": 999})

        captured = capsys.readouterr()

        # 出力された文字列が正しいJSONかパースしてみる
        log_json = json.loads(captured.err.strip())

        # GCPが要求する必須キーの検証
        assert log_json["severity"] == "INFO"
        assert log_json["message"] == "本番テストです"
        assert "time" in log_json

        # sourceLocation（ファイル名や行数）の検証
        assert "logging.googleapis.com/sourceLocation" in log_json
        assert (
            log_json["logging.googleapis.com/sourceLocation"]["file"]
            == "test_gcp_logger.py"
        )

        # extraデータの検証
        assert log_json["user_id"] == 999


def test_cloud_run_logging_exception(capsys: pytest.CaptureFixture[str]):
    """GCP環境で例外が発生した際に JSON に exception が含まれるかテスト"""
    with patch.dict(os.environ, {"K_SERVICE": "my-test-service"}):
        setup_logging()
        logger = logging.getLogger()

        try:
            raise ValueError("わざとエラーを起こします")  # noqa: EM101, TRY301
        except ValueError:
            logger.exception("エラーが発生しました")

        captured = capsys.readouterr()
        log_json = json.loads(captured.err.strip())

        assert log_json["severity"] == "ERROR"
        assert "exception" in log_json
        assert "ValueError: わざとエラーを起こします" in log_json["exception"]
