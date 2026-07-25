import pytest
from linebot.v3.messaging import ApiException, Message  # Message インポートを使用
from pytest_mock import AsyncMockType, MockerFixture

from clients.line_client import (
    get_user_name,
    push_message,
    reply_message,
    reply_message_safely,
    show_loading_animation,
)


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
        mock_msg_api.get_profile.side_effect = ApiException(
            status=404, reason="Not Found"
        )
        mock_exception = mocker.patch("clients.line_client.exception")

        name = await get_user_name(mock_msg_api, "U1234567890")

        assert name == "ユーザー"
        mock_exception.assert_called_once()


@pytest.mark.asyncio
class TestShowLoadingAnimation:
    """show_loading_animation 関数のテスト"""

    async def test_show_loading_animation_success(self, mock_msg_api: AsyncMockType):
        """正常系: ローディング表示リクエストが正しく呼び出されるか"""
        await show_loading_animation(mock_msg_api, "U1234567890", seconds=10)

        mock_msg_api.show_loading_animation.assert_called_once()
        call_args = mock_msg_api.show_loading_animation.call_args[0][0]
        assert call_args.chat_id == "U1234567890"
        assert call_args.loading_seconds == 10


@pytest.mark.asyncio
class TestReplyMessage:
    """reply_message 関数のテスト"""

    async def test_reply_message_success(self, mock_msg_api: AsyncMockType):
        """正常系: reply_message APIが正しく呼び出されるか"""
        messages: list[Message] = [
            Message.from_dict({"type": "text", "text": "テストメッセージ"})
        ]

        await reply_message(
            mock_msg_api, "reply_token_123", messages, notification_disabled=True
        )

        mock_msg_api.reply_message.assert_called_once()
        call_args = mock_msg_api.reply_message.call_args[0][0]
        assert call_args.reply_token == "reply_token_123"  # noqa: S105
        assert call_args.messages == messages
        assert call_args.notification_disabled is True


@pytest.mark.asyncio
class TestPushMessage:
    """push_message 関数のテスト"""

    async def test_push_message_success(self, mock_msg_api: AsyncMockType):
        """正常系: push_message APIが正しく呼び出されるか"""
        messages: list[Message] = [
            Message.from_dict({"type": "text", "text": "テストメッセージ"})
        ]

        await push_message(
            mock_msg_api, "U1234567890", messages, notification_disabled=False
        )

        mock_msg_api.push_message.assert_called_once()
        call_args = mock_msg_api.push_message.call_args[0][0]
        assert call_args.to == "U1234567890"
        assert call_args.messages == messages
        assert call_args.notification_disabled is False


@pytest.mark.asyncio
class TestReplyMessageSafely:
    """reply_message_safely 関数のテスト"""

    async def test_reply_message_safely_reply_success(
        self, mocker: MockerFixture, mock_msg_api: AsyncMockType
    ):
        """正常系: reply_message が成功した場合、push_message は呼ばれないか"""
        messages: list[Message] = [
            Message.from_dict({"type": "text", "text": "テストメッセージ"})
        ]
        spy_reply = mocker.patch(
            "clients.line_client.reply_message", new_callable=mocker.AsyncMock
        )
        spy_push = mocker.patch(
            "clients.line_client.push_message", new_callable=mocker.AsyncMock
        )

        await reply_message_safely(
            mock_msg_api, "U1234567890", "reply_token_123", messages
        )

        spy_reply.assert_called_once_with(
            mock_msg_api, "reply_token_123", messages, notification_disabled=False
        )
        spy_push.assert_not_called()

    async def test_reply_message_safely_fallback_to_push(
        self, mocker: MockerFixture, mock_msg_api: AsyncMockType
    ):
        """異常系: reply_message で ApiException の場合 push_message にフォールバック"""
        messages: list[Message] = [
            Message.from_dict({"type": "text", "text": "テストメッセージ"})
        ]

        mocker.patch(
            "clients.line_client.reply_message",
            side_effect=ApiException(status=400, reason="Invalid ReplyToken"),
        )
        spy_push = mocker.patch(
            "clients.line_client.push_message", new_callable=mocker.AsyncMock
        )
        mock_exception = mocker.patch("clients.line_client.exception")

        await reply_message_safely(
            mock_msg_api, "U1234567890", "reply_token_123", messages
        )

        mock_exception.assert_called_once()
        spy_push.assert_called_once_with(
            mock_msg_api, "U1234567890", messages, notification_disabled=False
        )
