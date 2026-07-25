from collections import deque
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import (
    FastAPI,
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
    AsyncApiClient,
    AsyncMessagingApi,
    Configuration,
)

from config.gcp_logger import error, exception, info, setup_logging
from config.settings import settings

setup_logging()

# メモリ上に直近100件のイベントIDをキャッシュ（注: 単一インスタンス前提）
processed_event_ids = deque(maxlen=100)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None]:
    """アプリ起動時に一度だけクライアントを生成し、終了時にクローズする"""
    configuration = Configuration(access_token=settings.line_channel_access_token)
    api_client = AsyncApiClient(configuration)

    app.state.msg_api = AsyncMessagingApi(api_client)
    app.state.parser = WebhookParser(settings.line_channel_secret)

    yield

    await api_client.close()


app = FastAPI(lifespan=lifespan, docs_url=None, redoc_url=None, openapi_url=None)


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
