from collections import deque

from google import genai
from google.genai import errors, types

from config.gcp_logger import exception
from config.settings import settings
from models.chat import ChatRequest

MAX_HISTORY_LEN = 40

# Client インスタンスはグローバルで保持（コネクションの再利用）
client = genai.Client(enterprise=True)

# インメモリで簡易的に会話履歴を保持（Max Instance=1 前提）
# { user_id: [ Content(role="user", ...), Content(role="model", ...) ] }
chat_histories: dict[str, deque[types.Content]] = {}


async def ask_gemini(request: ChatRequest) -> str:
    """Gemini API を呼び出して回答を生成する関数"""

    # ユーザーの過去履歴を取得（なければ空リスト）
    history = chat_histories.setdefault(request.user_id, deque(maxlen=MAX_HISTORY_LEN))

    # システムプロンプト（キャラ付けや回答スタイルの定義）
    system_instruction = (
        "あなたは親切でフレンドリーなLINE AIアシスタントです。"
        "回答はLINE画面で見やすいよう、要点をまとめてシンプルに答えてください。"
    )

    try:
        # 新しいセッションを作成して応答を得る
        chat = client.aio.chats.create(
            model=settings.model_name,
            config=types.GenerateContentConfig(
                system_instruction=system_instruction,
                temperature=0.7,
            ),
            history=list(history) or None,
        )

        # ユーザーの発言を送信
        user_content = request.user_text
        if request.extra_prompt:
            user_content = (
                f"【追加指示】メッセージ送信者の名前は「{request.user_name}」さんです。"
                f"{request.extra_prompt}\n\n{user_content}"
            )

        response = await chat.send_message(user_content)

        # 最新の履歴で更新（deque の maxlen によって自動的に古い順から削除される）
        updated_history = chat.get_history()
        history.clear()
        history.extend(updated_history)

    except errors.APIError as e:
        exception(f"Gemini API Error: {e.code} - {e.message}")
        return "申し訳ありません。一時的にAIが応答できませんでした。"
    except Exception as e:  # noqa: BLE001
        exception(f"Unexpected Error in ask_gemini: {e}")
        return "申し訳ありません。エラーが発生しました。"
    else:
        return response.text or "申し訳ありません。回答を生成できませんでした。"
