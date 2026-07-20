import asyncio
from collections import deque
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Annotated, Never

from fastapi import (
    Depends,
    FastAPI,
    Header,
    HTTPException,
    Request,
    Response,
    status,
)
from fastapi.exception_handlers import http_exception_handler
from fastapi.responses import JSONResponse
from linebot.v3 import WebhookParser
from linebot.v3.exceptions import InvalidSignatureError
from linebot.v3.messaging import (
    ApiException,
    AsyncApiClient,
    AsyncMessagingApi,
    Configuration,
    Message,
    ReplyMessageRequest,
    ShowLoadingAnimationRequest,
)
from linebot.v3.webhooks import (
    Event,
    FollowEvent,
    MessageEvent,
    TextMessageContent,
    UnfollowEvent,
    UserSource,
)
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from config.gcp_logger import error, exception, info, setup_logging

setup_logging()

# メモリ上に直近100件のイベントIDをキャッシュ（注: 単一インスタンス前提）
processed_event_ids = deque(maxlen=100)


class Settings(BaseSettings):
    line_channel_secret: str = Field(default=...)
    line_channel_access_token: str = Field(default=...)

    model_config = SettingsConfigDict(extra="ignore")


settings = Settings()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """アプリ起動時に一度だけクライアントを生成し、終了時にクローズする"""
    configuration = Configuration(access_token=settings.line_channel_access_token)
    api_client = AsyncApiClient(configuration)

    app.state.msg_api = AsyncMessagingApi(api_client)
    app.state.parser = WebhookParser(settings.line_channel_secret)

    yield

    await api_client.close()


app = FastAPI(lifespan=lifespan, docs_url=None, redoc_url=None, openapi_url=None)


async def get_events(
    request: Request, x_line_signature: Annotated[str, Header()]
) -> list[Event]:
    body_bytes = await request.body()
    body_str = body_bytes.decode("utf-8")

    parser: WebhookParser = request.app.state.parser
    events = parser.parse(body_str, x_line_signature)

    info(f"Request body: {body_str[:2000]}")

    # parse の as_payload は False なので list のはず
    if not isinstance(events, list):
        _bad_request("Invalid WebhookPayload")

    return events


async def get_user_name(msg_api: AsyncMessagingApi, user_id: str) -> str:
    """
    APIがエラーを吐いてもシステムをクラッシュさせず、デフォルト値「ユーザー」を返す安全弁
    """
    try:
        profile = await msg_api.get_profile(user_id)
    except ApiException as e:
        exception(f"Failed get_profile({user_id}): {e.status} {e.reason}")
        return "ユーザー"
    else:
        return profile.display_name


async def show_loading_animation(
    msg_api: AsyncMessagingApi, user_id: str, seconds: int = 20
) -> None:
    """loadingSecondsは5〜60秒の間で指定可能（デフォルトは20秒）"""
    request = ShowLoadingAnimationRequest(chatId=user_id, loadingSeconds=seconds)

    await msg_api.show_loading_animation(request)


async def reply_message(
    msg_api: AsyncMessagingApi,
    reply_token: str,
    messages: list[Message],
    *,
    notification_disabled: bool = False,
) -> None:
    reply_request = ReplyMessageRequest(
        replyToken=reply_token,
        messages=messages,
        notificationDisabled=notification_disabled,
    )

    await msg_api.reply_message(reply_request)


@app.post("/webhook")
async def webhook(
    request: Request,
    events: Annotated[list[Event], Depends(get_events)],
) -> Response:
    msg_api: AsyncMessagingApi = request.app.state.msg_api
    await async_bot_process(msg_api, events)

    return Response(content="OK", status_code=status.HTTP_200_OK)


async def async_bot_process(msg_api: AsyncMessagingApi, events: list[Event]) -> None:
    """
    LINEサーバーに対してOKをレスポンスした後の処理。
    """
    for event in events:
        # コールドスタートでレスポンスが遅れると同じイベントを再送してくる
        # At-Least-Once 配信ポリシーのため event が重複する可能性がある
        if event.webhook_event_id in processed_event_ids:
            info(f"Duplicate event ignored: {event.webhook_event_id}")
            continue  # 次のイベントの処理へスキップ

        # キャッシュに登録
        processed_event_ids.append(event.webhook_event_id)

        try:
            await process_event(msg_api, event)
        except Exception:  # noqa: BLE001
            exception("Unexpected event error")


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
        await reply_message(msg_api, event.reply_token, messages)
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

    # 重い処理（LLMの呼び出しなどを想定）
    await asyncio.sleep(10)
    ai_reply = f"{user_name}さんは「{user_text}」と言いましたね？"

    messages = [Message.from_dict({"type": "text", "text": ai_reply})]
    await reply_message(msg_api, reply_token, messages)


def _bad_request(message: str, exc: Exception | None = None) -> Never:
    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST, detail=message
    ) from exc


@app.exception_handler(InvalidSignatureError)
async def invalid_signature_handler(
    _request: Request, _exc: InvalidSignatureError
) -> JSONResponse:
    error("LINEからの通信の署名検証に失敗しました。")
    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content={"detail": "Invalid Signature"},
    )


@app.exception_handler(HTTPException)
async def client_exception_handler(request: Request, exc: HTTPException) -> Response:
    # FastAPI標準の挙動に任せる前にログする
    info(f"Client error: {request.url.path} {exc.status_code}")
    return await http_exception_handler(request, exc)


@app.exception_handler(Exception)
async def server_exception_handler(request: Request, _exc: Exception) -> JSONResponse:
    exception(f"Server error: {request.url.path}")
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "Internal Server Error"},
    )
