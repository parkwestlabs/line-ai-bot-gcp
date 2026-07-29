from linebot.v3.messaging import AsyncMessagingApi, Message
from linebot.v3.webhooks import (
    Event,
    FollowEvent,
    MessageEvent,
    TextMessageContent,
    UnfollowEvent,
    UserSource,
)

from clients.gemini_client import ask_gemini
from clients.line_client import (
    get_user_name,
    reply_message_safely,
    show_loading_animation,
)
from config.gcp_logger import info
from models.chat import ChatRequest


async def process_event(msg_api: AsyncMessagingApi, event: Event) -> None:
    # 送信元が User（個人）であり user_id が存在する場合のみ続行
    if not (isinstance(event.source, UserSource) and event.source.user_id):
        info(f"Skipping event: {event.source}")
        return

    user_id = event.source.user_id

    if isinstance(event, FollowEvent):
        user_name = await get_user_name(msg_api, user_id)
        info(f"友だち追加されました！ user_id: {user_id} (name: {user_name})")

        msg = f"{user_name}さん、友だち追加ありがとうございます！よろしくね！"
        messages = [Message.from_dict({"type": "text", "text": msg})]
        await reply_message_safely(msg_api, user_id, event.reply_token, messages)
        return

    if isinstance(event, UnfollowEvent):
        info(f"友だち削除(またはブロック)されました！ user_id: {user_id}")
        return

    if isinstance(event, MessageEvent):
        # MessageEvent には reply_token が必ず存在しているはず
        if not event.reply_token:  # pragma: no cover
            msg = f"MessageEvent missing reply_token: {event.webhook_event_id})"
            raise ValueError(msg)

        if isinstance(event.message, TextMessageContent):
            await handle_text_message(
                msg_api, user_id, event.reply_token, event.message
            )
        else:
            # TextMessageContent以外（スタンプや画像）はログだけ残して、スルーする
            info(f"[{user_id}]: ⚠️ テキスト以外を受信: {event.message.type}")


async def handle_text_message(
    msg_api: AsyncMessagingApi,
    user_id: str,
    reply_token: str,
    message_content: TextMessageContent,
) -> None:
    await show_loading_animation(msg_api, user_id)

    user_name = await get_user_name(msg_api, user_id)
    user_text = message_content.text
    info(f"[{user_id} ({user_name})]: {user_text}")

    request = ChatRequest(user_id=user_id, user_name=user_name, user_text=user_text)
    ai_reply = await ask_gemini(request)

    messages = [Message.from_dict({"type": "text", "text": ai_reply})]
    await reply_message_safely(msg_api, user_id, reply_token, messages)
