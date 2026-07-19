import os


# 💡 最初に環境変数をダミー値にセットする
# pytestがテストファイルを読み込む（インポートする）よりも「前」に実行させるため、
# セッション開始時に一番最初に呼ばれるフックを使用します。
def pytest_sessionstart():
    """pytestのセッション開始時に、Pydanticが読み込まれる前に環境変数を注入する"""
    os.environ["LINE_CHANNEL_SECRET"] = "dummy_secret_for_testing"  # noqa: S105
    os.environ["LINE_CHANNEL_ACCESS_TOKEN"] = "dummy_token_for_testing"  # noqa: S105
