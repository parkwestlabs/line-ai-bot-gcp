import pytest
from linebot.v3.messaging import ApiException
from pytest_mock import AsyncMockType, MockerFixture

from clients.line_client import get_user_name


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
        mock_exception = mocker.patch("clients.line_client.exception")

        name = await get_user_name(mock_msg_api, "U1234567890")

        assert name == "ユーザー"
        mock_exception.assert_called_once()
