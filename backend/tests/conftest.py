import importlib

import pytest
from fastapi.testclient import TestClient
from linebot.v3 import WebhookParser
from linebot.v3.messaging import AsyncMessagingApi
from linebot.v3.webhooks import Event, MessageEvent, UserSource
from pytest_mock import MockerFixture, MockType

import main


@pytest.fixture
def mock_msg_api(mocker: MockerFixture) -> AsyncMessagingApi:
    return mocker.AsyncMock()


@pytest.fixture
def mock_parser(mocker: MockerFixture) -> WebhookParser:
    return mocker.MagicMock(spec=WebhookParser)


# Note: using importlib to both invalidate cached modules and reload imported modules
# (thus refreshing the code & state). https://stackoverflow.com/a/71428106


@pytest.fixture
def client(mock_msg_api: AsyncMessagingApi, mock_parser: WebhookParser):
    """モックを受け取って、app.stateに仕込んでからclientを返す"""
    importlib.reload(main)
    app = main.app

    # with構文でTestClientを作成し、lifespan の起動・終了処理を正しく走らせる
    with TestClient(app) as test_client:
        app.state.msg_api = mock_msg_api
        app.state.parser = mock_parser
        yield test_client


@pytest.fixture
def client_with_error(mock_parser: MockType):
    """webhookのエンドポイントで予期せぬエラーをわざと起こすためのクライアント"""
    importlib.reload(main)
    app = main.app

    mock_parser.parse.side_effect = Exception("Fatal database/server error")

    with TestClient(app, raise_server_exceptions=False) as test_client:
        app.state.parser = mock_parser
        yield test_client


@pytest.fixture
def dummy_event(mocker: MockerFixture) -> Event:
    """テスト用の基本となるダミーイベントを作成するフィクスチャ"""
    event = mocker.MagicMock(spec=MessageEvent)
    event.webhook_event_id = "dummy_event_id_123"
    event.reply_token = "dummy_reply_token"  # noqa: S105

    mock_source = mocker.MagicMock(spec=UserSource)
    mock_source.user_id = "dummy_user_id"
    event.source = mock_source

    return event
