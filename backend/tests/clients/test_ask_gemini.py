from unittest.mock import AsyncMock, MagicMock

import pytest
from google import genai
from google.genai import chats, errors, types
from pytest_mock import MockerFixture, MockType

from clients.gemini_client import ask_gemini, chat_histories
from models.chat import ChatRequest


@pytest.fixture(autouse=True)
def clear_chat_histories():
    """各テスト実行前に会話履歴（インメモリ）をクリアする"""
    chat_histories.clear()
    yield
    chat_histories.clear()


@pytest.fixture
def mock_ai_client(mocker: MockerFixture):
    """すべてのテストで gemini client を自動的にモック化する"""
    return mocker.patch("clients.gemini_client.client", spec=genai.Client)


@pytest.mark.asyncio
async def test_ask_gemini_success(mock_ai_client: MockType):
    """正常系: Gemini API が正常に応答を返すケース"""
    request = ChatRequest(
        user_id="user_123",
        user_name="テスト太郎",
        user_text="こんにちは",
        extra_prompt="丁寧に応答してください",
    )

    mock_response = MagicMock()
    mock_response.text = "こんにちは！何かお手伝いできますか？"

    mock_chat = AsyncMock(spec=chats.AsyncChat)
    mock_chat.send_message.return_value = mock_response

    mock_history_item = MagicMock(spec=types.Content)
    mock_chat.get_history.return_value = [mock_history_item]

    mock_ai_client.aio.chats.create.return_value = mock_chat

    result = await ask_gemini(request)

    assert result == "こんにちは！何かお手伝いできますか？"

    # API へ送信されたプロンプト形式の検証
    mock_chat.send_message.assert_called_once()
    sent_prompt = mock_chat.send_message.call_args[0][0]
    assert "テスト太郎" in sent_prompt
    assert "丁寧に応答してください" in sent_prompt
    assert "こんにちは" in sent_prompt

    # 履歴が更新されているか確認
    assert len(chat_histories["user_123"]) == 1
    assert list(chat_histories["user_123"]) == [mock_history_item]


@pytest.mark.asyncio
async def test_ask_gemini_response_text_none(mock_ai_client: MockType):
    """正常系（エッジケース）: レスポンスは返ってきたが text が None のケース"""
    request = ChatRequest(
        user_id="user_123",
        user_name="テスト太郎",
        user_text="不適切な入力",
    )

    mock_response = MagicMock()
    mock_response.text = None  # セーフティフィルター等で None になった場合

    mock_chat = AsyncMock(spec=chats.AsyncChat)
    mock_chat.send_message.return_value = mock_response
    mock_chat.get_history.return_value = []

    mock_ai_client.aio.chats.create.return_value = mock_chat

    result = await ask_gemini(request)

    # フォールバックメッセージが返るか確認
    assert result == "申し訳ありません。回答を生成できませんでした。"


@pytest.mark.asyncio
async def test_ask_gemini_api_error(mock_ai_client: MockType, mocker: MockerFixture):
    """異常系: Google APIError が発生するケース"""
    request = ChatRequest(
        user_id="user_123",
        user_name="テスト太郎",
        user_text="エラーテスト",
    )

    api_error = errors.APIError(code=500, response=MagicMock(), response_json="")
    mock_ai_client.aio.chats.create.side_effect = api_error
    mock_logger = mocker.patch("clients.gemini_client.exception")

    result = await ask_gemini(request)

    assert result == "申し訳ありません。一時的にAIが応答できませんでした。"
    mock_logger.assert_called_once()  # ログ出力が呼ばれたか


@pytest.mark.asyncio
async def test_ask_gemini_exception(mock_ai_client: MockType, mocker: MockerFixture):
    """異常系: 予期せぬ例外（例: ネットワーク断など）が発生するケース"""
    request = ChatRequest(
        user_id="user_123",
        user_name="テスト太郎",
        user_text="エラーテスト",
        extra_prompt=None,
    )

    mock_ai_client.aio.chats.create.side_effect = RuntimeError("Unexpected Error")
    mock_logger = mocker.patch("clients.gemini_client.exception")

    result = await ask_gemini(request)

    assert result == "申し訳ありません。エラーが発生しました。"
    mock_logger.assert_called_once()  # ログ出力が呼ばれたか
