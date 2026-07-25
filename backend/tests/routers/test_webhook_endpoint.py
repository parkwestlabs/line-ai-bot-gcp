from fastapi import status
from fastapi.testclient import TestClient
from linebot.v3.exceptions import InvalidSignatureError
from pytest_mock import MockType


class TestWebhookEndpoint:
    """/webhook エンドポイントのテスト"""

    def test_webhook_success(self, client: TestClient, mock_parser: MockType):
        """正常系: 署名が正しく、タスクが登録されて 200 OK が返るか"""
        # 💡 モック化した parser がダミーのリストを返すように設定
        mock_parser.parse.return_value = []

        # 💡 TestClient を直接使えば、async with も httpx.ASGITransport も不要
        response = client.post(
            "/webhook",
            headers={"X-Line-Signature": "valid_signature"},
            content="dummy_body",
        )

        assert response.status_code == status.HTTP_200_OK
        assert response.text == "OK"
        mock_parser.parse.assert_called_once_with("dummy_body", "valid_signature")

    def test_webhook_missing_signature(self, client: TestClient):
        """異常系: 署名ヘッダーがない場合に FastAPIが422（または400）を返すか"""
        response = client.post(
            "/webhook",
            content="dummy_body",
            # X-Line-Signature ヘッダーを入れない
        )

        # 注: main.py で必須（Annotated[str, Header()]）にしたため、
        # FastAPI標準の挙動であれば 422 Unprocessable Entity が返ります
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT
        assert response.json()["detail"] == [
            {
                "type": "missing",
                "loc": ["header", "x-line-signature"],
                "msg": "Field required",
                "input": None,
            }
        ]

    def test_webhook_invalid_signature(self, client: TestClient, mock_parser: MockType):
        """異常系: 署名検証に失敗した場合に例外ハンドラーが作動するか"""
        # parser.parse が InvalidSignatureError を投げるように設定
        mock_parser.parse.side_effect = InvalidSignatureError()

        response = client.post(
            "/webhook",
            headers={"X-Line-Signature": "invalid_signature"},
            content="dummy_body",
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert response.json()["detail"] == "Invalid Signature"

    def test_webhook_invalid_payload_type(
        self, client: TestClient, mock_parser: MockType
    ):
        """異常系: parse結果がリストではない場合に 400 になるか"""
        mock_parser.parse.return_value = "not_a_list"

        response = client.post(
            "/webhook",
            headers={"X-Line-Signature": "valid_signature"},
            content="dummy_body",
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert response.json()["detail"] == "Invalid WebhookPayload"

    def test_webhook_server_error(self, client_with_error: TestClient):
        """異常系: サーバー内部で予期せぬ例外が発生した際、500 Errorを返すか"""
        response = client_with_error.post(
            "/webhook",
            headers={"X-Line-Signature": "valid_signature"},
            content="dummy_body",
        )
        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
        assert response.json()["detail"] == "Internal Server Error"
