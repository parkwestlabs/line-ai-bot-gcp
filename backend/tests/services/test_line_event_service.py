import pytest
from linebot.v3.messaging import AsyncMessagingApi
from linebot.v3.webhooks import (
    Event,
    FollowEvent,
    GroupSource,
    MessageEvent,
    StickerMessageContent,
    TextMessageContent,
    UnfollowEvent,
)
from pytest_mock import AsyncMockType, MockerFixture, MockType

from main import processed_event_ids
from routers.webhook import async_bot_process
from services.line_event_service import process_event


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
        mock_process_event = mocker.patch(
            "routers.webhook.process_event", mocker.AsyncMock()
        )

        await async_bot_process(mock_msg_api, [dummy_event])

        mock_process_event.assert_called_once_with(mock_msg_api, dummy_event)

    async def test_async_bot_process_duplicate_event(
        self, mocker: MockerFixture, mock_msg_api: AsyncMessagingApi
    ):
        """正常系: 同じwebhook_event_idが連続で届いた際、2回目は重複として排除するか"""
        processed_event_ids.clear()

        mock_process_event = mocker.patch(
            "routers.webhook.process_event", mocker.AsyncMock()
        )
        # 💡 config.gcp_logger ではなく、routers.webhookのパッチターゲットを修正
        mock_info = mocker.patch("routers.webhook.info")

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
            "routers.webhook.process_event",
            mocker.AsyncMock(side_effect=ValueError("LINE APIのエラーなど")),
        )
        mock_exception = mocker.patch("routers.webhook.exception")

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
        mocker.patch(
            "services.line_event_service.get_user_name",
            mocker.AsyncMock(return_value="テスト太郎"),
        )
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
        mocker.patch(
            "services.line_event_service.get_user_name",
            mocker.AsyncMock(return_value="テスト太郎"),
        )

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
