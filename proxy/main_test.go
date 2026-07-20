package main

import (
	"bytes"
	"crypto/hmac"
	"crypto/sha256"
	"encoding/base64"
	"net/http"
	"net/http/httptest"
	"os"
	"testing"
	"time"
)

// テスト用のヘルパー関数: HMAC-SHA256 署名を生成する
func generateSignature(secret string, body []byte) string {
	hash := hmac.New(sha256.New, []byte(secret))
	hash.Write(body)
	return base64.StdEncoding.EncodeToString(hash.Sum(nil))
}

// 1. 署名検証 (verifySignature) の単体テスト
func TestVerifySignature(t *testing.T) {
	secret := "test_secret"
	body := []byte(`{"events":[]}`)

	validSig := generateSignature(secret, body)
	invalidSig := "invalid_signature_base64"

	if !verifySignature(secret, body, validSig) {
		t.Errorf("Expected signature to be valid, but got invalid")
	}

	if verifySignature(secret, body, invalidSig) {
		t.Errorf("Expected signature to be invalid, but got valid")
	}
}

// 2. イベント重複判定 (isDuplicateID) の単体テスト
func TestIsDuplicateID(t *testing.T) {
	eventID := "evt_test_001"
	ttl := 100 * time.Millisecond

	// 1回目: 新規登録なので false が返るはず
	if isDuplicateID(eventID, ttl) {
		t.Errorf("First call for %s should not be marked as duplicate", eventID)
	}

	// 2回目: キャッシュ内にあるので true (重複) が返るはず
	if !isDuplicateID(eventID, ttl) {
		t.Errorf("Second call for %s should be marked as duplicate", eventID)
	}

	// TTL時間経過を待つ
	time.Sleep(150 * time.Millisecond)

	// TTL経過後: キャッシュが削除されているため false が返るはず
	if isDuplicateID(eventID, ttl) {
		t.Errorf("Call after TTL for %s should not be marked as duplicate", eventID)
	}
}

// 3. Webhook ハンドラ (handleWebhook) の統合テスト
func TestHandleWebhook(t *testing.T) {
	secret := "my_secret"
	os.Setenv("LINE_CHANNEL_SECRET", secret)

	// モック用のダミーPythonサーバー（転送テスト用）
	mockPythonServer := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.WriteHeader(http.StatusOK)
	}))
	defer mockPythonServer.Close()
	os.Setenv("PYTHON_BACKEND_URL", mockPythonServer.URL)

	t.Run("GETリクエストは 405 Method Not Allowed を返すこと", func(t *testing.T) {
		req := httptest.NewRequest(http.MethodGet, "/webhook", nil)
		rec := httptest.NewRecorder()

		handleWebhook(rec, req)

		if rec.Code != http.StatusMethodNotAllowed {
			t.Errorf("Expected status 405, got %d", rec.Code)
		}
	})

	t.Run("不正な署名の場合は 400 Bad Request を返すこと", func(t *testing.T) {
		body := []byte(`{"events":[]}`)
		req := httptest.NewRequest(http.MethodPost, "/webhook", bytes.NewBuffer(body))
		req.Header.Set("X-Line-Signature", "wrong_signature")
		rec := httptest.NewRecorder()

		handleWebhook(rec, req)

		if rec.Code != http.StatusBadRequest {
			t.Errorf("Expected status 400, got %d", rec.Code)
		}
	})

	t.Run("正常なリクエストは 200 OK を返し、2回目の同一リクエストは重複として処理されること", func(t *testing.T) {
		body := []byte(`{"events":[{"webhookEventId":"dup_test_123"}]}`)
		sig := generateSignature(secret, body)

		// 1回目のリクエスト（正常）
		req1 := httptest.NewRequest(http.MethodPost, "/webhook", bytes.NewBuffer(body))
		req1.Header.Set("X-Line-Signature", sig)
		rec1 := httptest.NewRecorder()

		handleWebhook(rec1, req1)

		if rec1.Code != http.StatusOK {
			t.Errorf("First request expected status 200, got %d", rec1.Code)
		}

		// 2回目のリクエスト（同じ webhookEventId なので重複検知）
		req2 := httptest.NewRequest(http.MethodPost, "/webhook", bytes.NewBuffer(body))
		req2.Header.Set("X-Line-Signature", sig)
		rec2 := httptest.NewRecorder()

		handleWebhook(rec2, req2)

		if rec2.Code != http.StatusOK {
			t.Errorf("Duplicate request expected status 200, got %d", rec2.Code)
		}
	})
}
