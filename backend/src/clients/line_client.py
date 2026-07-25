from linebot.v3.messaging import (
    ApiException,
    AsyncMessagingApi,
    Message,
    PushMessageRequest,
    ReplyMessageRequest,
    ShowLoadingAnimationRequest,
)

from config.gcp_logger import exception


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


async def push_message(
    msg_api: AsyncMessagingApi,
    user_id: str,
    messages: list[Message],
    *,
    notification_disabled: bool = False,
) -> None:

    push_request = PushMessageRequest(
        to=user_id,
        messages=messages,
        notificationDisabled=notification_disabled,
        customAggregationUnits=None,
    )
    await msg_api.push_message(push_request)


async def reply_message_safely(
    msg_api: AsyncMessagingApi,
    user_id: str,
    reply_token: str,
    messages: list[Message],
    *,
    notification_disabled: bool = False,
) -> None:
    try:
        await reply_message(
            msg_api, reply_token, messages, notification_disabled=notification_disabled
        )
    except ApiException as e:
        exception(f"Reply failed ({e.status}), fallback to Push Message for {user_id}")
        await push_message(
            msg_api, user_id, messages, notification_disabled=notification_disabled
        )
