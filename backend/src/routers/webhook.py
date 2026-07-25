from typing import Annotated, Never

from fastapi import Depends, Header, HTTPException, Request, Response, status
from linebot.v3 import WebhookParser
from linebot.v3.messaging import AsyncMessagingApi
from linebot.v3.webhooks import Event

from config.gcp_logger import exception, info
from main import app, processed_event_ids
from services.line_event_service import process_event


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


def _bad_request(message: str, exc: Exception | None = None) -> Never:
    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST, detail=message
    ) from exc


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
