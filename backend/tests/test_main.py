import pytest
from fastapi import status
from fastapi.testclient import TestClient
from linebot.v3 import WebhookParser
from linebot.v3.exceptions import InvalidSignatureError
from linebot.v3.messaging import ApiException, AsyncApiClient, AsyncMessagingApi
from linebot.v3.webhooks import (
    Event,
    FollowEvent,
    GroupSource,
    MessageEvent,
    StickerMessageContent,
    TextMessageContent,
    UnfollowEvent,
    UserSource,
)
from pytest_mock import AsyncMockType, MockerFixture, MockType

from main import (
    app,
    async_bot_process,
    get_user_name,
    process_event,
    processed_event_ids,
)

# ==========================================
# 🛠️ FIXTURES (フィクスチャ)
# ==========================================


@pytest.fixture
def mock_msg_api(mocker: MockerFixture) -> AsyncMessagingApi:
    return mocker.AsyncMock()


@pytest.fixture
def mock_parser(mocker: MockerFixture) -> WebhookParser:
    return mocker.MagicMock(spec=WebhookParser)


@pytest.fixture
def client(mock_msg_api: AsyncMessagingApi, mock_parser: WebhookParser):
    """モックを受け取って、app.stateに仕込んでからclientを返す"""
    app.state.msg_api = mock_msg_api
    app.state.parser = mock_parser
    return TestClient(app)


@pytest.fixture
def client_with_error(mock_parser: MockType):
    """webhookのエンドポイントで予期せぬエラーをわざと起こすためのクライアント"""
    mock_parser.parse.side_effect = Exception("Fatal database/server error")
    app.state.parser = mock_parser
    return TestClient(app, raise_server_exceptions=False)


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


# ==========================================
# 🧪 TEST CASES (テストケース)
# ==========================================


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


class TestWebhookEndpoint:
    """/webhook エンドポイントのテスト"""

    def test_webhook_success(self, client: TestClient, mock_parser: MockType):
        """正常系: 署名が正しく、タスクが登録されて 200 OK が返るか"""
        # 💡 モック化した parser がダミーのリストを返すように設定
        mock_parser.parse.return_value = []

        # 💡 TestClient を直接使えば、async with も httpx.ASGITransport も不要
        response = client.post(
            "/webhook",
            headers={"X-Line-Signature": "valid_signature"},
            content="dummy_body",
        )

        assert response.status_code == status.HTTP_200_OK
        assert response.text == "OK"
        mock_parser.parse.assert_called_once_with("dummy_body", "valid_signature")

    def test_webhook_missing_signature(self, client: TestClient):
        """異常系: 署名ヘッダーがない場合に FastAPIが422（または400）を返すか"""
        response = client.post(
            "/webhook",
            content="dummy_body",
            # X-Line-Signature ヘッダーを入れない
        )

        # 注: main.py で必須（Annotated[str, Header()]）にしたため、
        # FastAPI標準の挙動であれば 422 Unprocessable Entity が返ります
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT
        assert response.json()["detail"] == [
            {
                "type": "missing",
                "loc": ["header", "x-line-signature"],
                "msg": "Field required",
                "input": None,
            }
        ]

    def test_webhook_invalid_signature(self, client: TestClient, mock_parser: MockType):
        """異常系: 署名検証に失敗した場合に例外ハンドラーが作動するか"""
        # parser.parse が InvalidSignatureError を投げるように設定
        mock_parser.parse.side_effect = InvalidSignatureError()

        response = client.post(
            "/webhook",
            headers={"X-Line-Signature": "invalid_signature"},
            content="dummy_body",
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert response.json()["detail"] == "Invalid Signature"

    def test_webhook_invalid_payload_type(
        self, client: TestClient, mock_parser: MockType
    ):
        """異常系: parse結果がリストではない場合に 400 になるか"""
        mock_parser.parse.return_value = "not_a_list"

        response = client.post(
            "/webhook",
            headers={"X-Line-Signature": "valid_signature"},
            content="dummy_body",
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert response.json()["detail"] == "Invalid WebhookPayload"

    def test_webhook_server_error(self, client_with_error: TestClient):
        """異常系: サーバー内部で予期せぬ例外が発生した際、500 Errorを返すか"""
        response = client_with_error.post(
            "/webhook",
            headers={"X-Line-Signature": "valid_signature"},
            content="dummy_body",
        )
        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
        assert response.json()["detail"] == "Internal Server Error"


@pytest.mark.asyncio
class TestBotProcess:
    """イベント処理ロジック (process_event) のテスト"""

    async def test_async_bot_process(
        self,
        mocker: MockerFixture,
        mock_msg_api: AsyncMessagingApi,
        dummy_event: Event,
    ):
        """正常系: 複数のイベントが渡された際、正しく処理が分配されるか"""
        mock_process_event = mocker.patch("main.process_event", mocker.AsyncMock())

        await async_bot_process(mock_msg_api, [dummy_event])

        mock_process_event.assert_called_once_with(mock_msg_api, dummy_event)

    async def test_async_bot_process_duplicate_event(
        self, mocker: MockerFixture, mock_msg_api: AsyncMessagingApi
    ):
        """正常系: 同じwebhook_event_idが連続で届いた際、2回目は重複として排除するか"""
        processed_event_ids.clear()

        mock_process_event = mocker.patch("main.process_event", mocker.AsyncMock())
        # 💡 config.gcp_logger ではなく、mainのパッチターゲットを修正
        mock_info = mocker.patch("main.info")

        dummy_id = "evt_duplicate_test_12345"
        mock_event1 = mocker.MagicMock()
        mock_event1.webhook_event_id = dummy_id

        mock_event2 = mocker.MagicMock()
        mock_event2.webhook_event_id = dummy_id

        events = [mock_event1, mock_event2]
        await async_bot_process(mock_msg_api, events)

        # 1回目だけ呼ばれる
        mock_process_event.assert_called_once_with(mock_msg_api, mock_event1)
        # 2回目は重複ログが出る
        mock_info.assert_called_once_with(f"Duplicate event ignored: {dummy_id}")

    async def test_async_bot_process_exception(
        self, mocker: MockerFixture, mock_msg_api: AsyncMessagingApi, dummy_event: Event
    ):
        """異常系: 例外が発生しても、バックグラウンドタスクがクラッシュしないか"""
        mock_process_event = mocker.patch(
            "main.process_event",
            mocker.AsyncMock(side_effect=ValueError("LINE APIのエラーなど")),
        )
        mock_exception = mocker.patch("main.exception")

        await async_bot_process(mock_msg_api, [dummy_event])

        mock_process_event.assert_called_once_with(mock_msg_api, dummy_event)
        mock_exception.assert_called_once_with("Unexpected event error")

    async def test_process_event_text_message(
        self,
        mocker: MockerFixture,
        mock_msg_api: AsyncMockType,
        dummy_event: MessageEvent,
    ):
        """正常系: テキストメッセージを受信した際、返信処理が走るか"""
        mocker.patch("main.get_user_name", mocker.AsyncMock(return_value="テスト太郎"))
        mocker.patch("asyncio.sleep", mocker.AsyncMock())  # 10秒待つのをスキップ

        # メッセージ内容をテキストに設定
        mock_message = mocker.MagicMock(spec=TextMessageContent)
        mock_message.text = "こんにちは"
        dummy_event.message = mock_message

        await process_event(mock_msg_api, dummy_event)

        # reply_message が1回呼ばれたことを検証
        mock_msg_api.reply_message.assert_called_once()

        # 呼び出された際の引数（ReplyMessageRequest）を検証
        args = mock_msg_api.reply_message.call_args[0][0]
        assert args.reply_token == "dummy_reply_token"  # noqa: S105
        assert args.messages[0].text == "テスト太郎さんは「こんにちは」と言いましたね？"

    async def test_process_event_other_message(
        self,
        mocker: MockerFixture,
        mock_msg_api: AsyncMockType,
        dummy_event: MessageEvent,
    ):
        """正常系: スタンプなどテキスト以外のメッセージで返信が走らないか"""
        mock_sticker_message = mocker.MagicMock(spec=StickerMessageContent)
        mock_sticker_message.type = "sticker"
        dummy_event.message = mock_sticker_message

        await process_event(mock_msg_api, dummy_event)

        mock_msg_api.reply_message.assert_not_called()

    async def test_process_event_follow_message(
        self,
        mocker: MockerFixture,
        mock_msg_api: AsyncMockType,
        dummy_event: MessageEvent,
    ):
        """正常系: 友だち追加（FollowEvent）された際、歓迎メッセージの返信が走るか"""
        mocker.patch("main.get_user_name", mocker.AsyncMock(return_value="テスト太郎"))

        mock_follow_event = mocker.MagicMock(spec=FollowEvent)
        mock_follow_event.source = dummy_event.source
        mock_follow_event.reply_token = dummy_event.reply_token

        await process_event(mock_msg_api, mock_follow_event)

        mock_msg_api.reply_message.assert_called_once()
        args = mock_msg_api.reply_message.call_args[0][0]
        assert (
            args.messages[0].text
            == "テスト太郎さん、友だち追加ありがとうございます！よろしくね！"
        )

    async def test_process_event_unfollow_message(
        self,
        mocker: MockerFixture,
        mock_msg_api: AsyncMockType,
        dummy_event: MessageEvent,
    ):
        """正常系: ブロック（UnfollowEvent）された際、返信はせず安全に処理が終わるか"""
        mock_unfollow_event = mocker.MagicMock(spec=UnfollowEvent)
        mock_unfollow_event.source = dummy_event.source

        await process_event(mock_msg_api, mock_unfollow_event)

        mock_msg_api.reply_message.assert_not_called()

    async def test_process_event_not_user_source(
        self, mocker: MockerFixture, mock_msg_api: AsyncMockType
    ):
        """異常系: 送信元がユーザー以外（GroupSourceなど）の場合、スルーされるか"""
        mock_group_event = mocker.MagicMock(spec=MessageEvent)
        mock_group_event.source = mocker.MagicMock(spec=GroupSource)

        await process_event(mock_msg_api, mock_group_event)

        mock_msg_api.reply_message.assert_not_called()

    async def test_process_event_user_source_without_id(
        self, mock_msg_api: AsyncMockType, dummy_event: MockType
    ):
        """異常系: UserSource だが user_id が存在しない場合、何もせずスルーされるか"""
        dummy_event.source.user_id = None

        await process_event(mock_msg_api, dummy_event)

        mock_msg_api.reply_message.assert_not_called()


@pytest.mark.asyncio
class TestGetUserName:
    """get_user_name 関数のテスト"""

    async def test_get_user_name_success(
        self, mocker: MockerFixture, mock_msg_api: AsyncMockType
    ):
        """正常系: プロフィールが正常に取得できた場合、display_nameを返すか"""
        mock_profile = mocker.MagicMock()
        mock_profile.display_name = "テスト太郎"
        mock_msg_api.get_profile.return_value = mock_profile

        name = await get_user_name(mock_msg_api, "U1234567890")

        assert name == "テスト太郎"
        mock_msg_api.get_profile.assert_called_once_with("U1234567890")

    async def test_get_user_name_failure(
        self, mocker: MockerFixture, mock_msg_api: AsyncMockType
    ):
        """異常系: API呼び出しでApiExceptionが起きても『ユーザー』を返すか"""
        # わざと例外を投げるように設定
        mock_msg_api.get_profile.side_effect = ApiException(
            status=404, reason="Not Found"
        )
        mock_exception = mocker.patch("main.exception")

        name = await get_user_name(mock_msg_api, "U1234567890")

        assert name == "ユーザー"
        mock_exception.assert_called_once()
