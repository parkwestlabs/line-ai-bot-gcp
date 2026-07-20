package main

import (
	"bytes"
	"crypto/hmac"
	"crypto/sha256"
	"encoding/base64"
	"encoding/json"
	"io"
	"log"
	"net/http"
	"os"
	"sync"
	"time"
)

// LINE bot go proxy
// - event id 重複チェックと署名検証を行う門番役
// - 非同期で Python backend に body を転送する
// - 軽量化のため LINE SDK（LINE Go SDK v8）への依存はしない

// webhookEventId だけをピンポイントで抜き出すための軽量な構造体
type LineWebhookRequest struct {
	Events []LineEvent `json:"events"`
}

type LineEvent struct {
	WebhookEventID string `json:"webhookEventId"`
}

// 重複チェック用のメモリキャッシュ（スレッドセーフな Map）
var eventCache = sync.Map{}

func main() {
	requiresEnv("LINE_CHANNEL_SECRET")
	requiresEnv("PYTHON_BACKEND_URL")

	// ポート番号は環境変数 PORT（Cloud Runの仕様）に従い、なければ8080にする
	port := os.Getenv("PORT")
	if port == "" {
		port = "8080"
	}

	http.HandleFunc("/webhook", handleWebhook)

	log.Printf("Proxy server started on port %s...\n", port)
	if err := http.ListenAndServe(":"+port, nil); err != nil {
		log.Fatalf("Server failed to start: %v", err)
	}
}

func requiresEnv(key string) {
	if os.Getenv(key) == "" {
		log.Fatalf("Required env var not found: %s", key)
	}
}

func handleWebhook(w http.ResponseWriter, req *http.Request) {
	// POST以外は却下
	if req.Method != http.MethodPost {
		w.WriteHeader(http.StatusMethodNotAllowed)
		return
	}

	// リクエストボディの読み込み
	body, err := io.ReadAll(req.Body)
	if err != nil {
		log.Printf("Failed to read request body: %v", err)
		w.WriteHeader(http.StatusInternalServerError)
		return
	}

	// 署名（Signature）の検証
	secret := os.Getenv("LINE_CHANNEL_SECRET")
	signature := req.Header.Get("X-Line-Signature")

	if !verifySignature(secret, body, signature) {
		log.Println("Webhook error: invalid signature")
		w.WriteHeader(http.StatusBadRequest)
		return
	}

	// イベント重複チェック（すでに処理中のイベントならここでブロックして200 OKだけ返す）
	if isDuplicateEvent(body) {
		log.Println("Duplicate event detected, skipped forwarding.")
		w.WriteHeader(http.StatusOK)
		return
	}

	// 即座に LINE に 200 OK を返す
	w.WriteHeader(http.StatusOK)

	// 非同期で body を Python backend へ転送
	go forwardToPython(signature, body)
}

// 署名検証（HMAC-SHA256） ➔ Web業界の標準規格であり、LINE公式仕様。
func verifySignature(secret string, body []byte, signature string) bool {
	hash := hmac.New(sha256.New, []byte(secret))
	hash.Write(body)
	expectedSignature := base64.StdEncoding.EncodeToString(hash.Sum(nil))
	return hmac.Equal([]byte(signature), []byte(expectedSignature))
}

// WebhookEventID が重複していれば true を返す
func isDuplicateEvent(body []byte) bool {
	var request LineWebhookRequest

	// webhookEventId だけを抽出（失敗した場合は安全のため転送を通す）
	if err := json.Unmarshal(body, &request); err != nil {
		return false
	}

	for _, event := range request.Events {
		if event.WebhookEventID == "" {
			continue
		}

		// 過去5分以内に同じ WebhookEventID を受信したかチェック
		if isDuplicateID(event.WebhookEventID, 5*time.Minute) {
			return true // 重複あり！
		}
	}

	return false
}

// isDuplicateID は指定されたIDがキャッシュに存在するかをチェック
// その後、指定された時間（TTL）だけIDをメモリに保持します
func isDuplicateID(eventID string, ttl time.Duration) bool {
	_, loaded := eventCache.LoadOrStore(eventID, time.Now())
	if loaded {
		return true // 重複（Dup）している！
	}

	// 新規 ID の場合、指定時間後に自動削除するタイマーを起動
	go func() {
		time.Sleep(ttl)
		eventCache.Delete(eventID)
	}()

	return false // 重複していない（新規）
}

// Python（FastAPI）に body を POST する
func forwardToPython(signature string, body []byte) {
	pythonURL := os.Getenv("PYTHON_BACKEND_URL")

	outReq, err := http.NewRequest(http.MethodPost, pythonURL, bytes.NewBuffer(body))
	if err != nil {
		log.Printf("Failed to create request for Python: %v", err)
		return
	}

	outReq.Header.Set("Content-Type", "application/json")
	outReq.Header.Set("X-Line-Signature", signature)

	resp, err := http.DefaultClient.Do(outReq)
	if err != nil {
		log.Printf("Failed to forward event to Python: %v", err)
		return
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		log.Printf("Python backend return non-200 status: %d", resp.StatusCode)
	}
}
