from linebot.v3.messaging import (
    ApiException,
    AsyncMessagingApi,
    Message,
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
