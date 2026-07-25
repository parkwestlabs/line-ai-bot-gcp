import pytest
from fastapi.testclient import TestClient
from linebot.v3 import WebhookParser
from linebot.v3.messaging import AsyncApiClient, AsyncMessagingApi
from pytest_mock import MockerFixture

from main import app


@pytest.mark.asyncio
class TestLifespan:
    """lifespan (アプリ起動・終了時の処理) のテスト"""

    async def test_lifespan_flow(self, mocker: MockerFixture):
        """正常系: アプリ起動時に初期化され、終了時に適切にクローズされるか"""
        # 1. 内部で生成される AsyncApiClient とその close メソッドをモック化
        mock_close = mocker.AsyncMock()
        mock_client_instance = mocker.MagicMock(spec=AsyncApiClient)
        mock_client_instance.close = mock_close

        # AsyncApiClient クラスそのものをパッチして、上記モックを返すようにする
        mocker.patch("main.AsyncApiClient", return_value=mock_client_instance)

        # 2. TestClient を with 構文で実行（これで lifespan がトリガーされる）
        # ※ 既存の client フィクスチャは内部で app.state を上書きしてしまうため、
        # lifespan 本体の挙動を検証するためにここでは生の app からクライアントを作ります
        with TestClient(app):
            # --- 💡 ここはアプリ起動中（lifespan 内の yield 部分） ---

            # state に各インスタンスが正しくセットされているか検証
            assert hasattr(app.state, "msg_api")
            assert hasattr(app.state, "parser")
            assert isinstance(app.state.msg_api, AsyncMessagingApi)
            assert isinstance(app.state.parser, WebhookParser)

            # まだアプリは終了していないので、close は呼ばれていないはず
            mock_close.assert_not_called()

        # --- 💡 ここはアプリ終了後（with を抜けた後） ---

        # クライアントのクローズ処理が確実に実行されたかを検証
        mock_close.assert_called_once()
