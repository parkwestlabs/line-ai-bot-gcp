from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, Request, Response, status
from linebot.v3 import WebhookParser
from linebot.v3.messaging import AsyncMessagingApi
from linebot.v3.webhooks import Event

from config.gcp_logger import exception, info
from services.line_event_service import process_event

router = APIRouter()


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
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Invalid WebhookPayload")

    return events


@router.post("/webhook")
async def webhook(
    request: Request,
    events: Annotated[list[Event], Depends(get_events)],
) -> Response:
    msg_api: AsyncMessagingApi = request.app.state.msg_api
    await async_bot_process(msg_api, events)

    return Response(content="OK", status_code=status.HTTP_200_OK)


async def async_bot_process(msg_api: AsyncMessagingApi, events: list[Event]) -> None:
    """
    Go側で非同期転送・重複排除済みのため、重複考慮はせず、直接処理を呼ぶ
    """
    for event in events:
        try:
            await process_event(msg_api, event)
        except Exception:  # noqa: BLE001
            exception("Unexpected event error")
