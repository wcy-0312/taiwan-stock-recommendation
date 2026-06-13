# 台股智能雷達 LINE Bot — Operator Guide

## LINE OA 回應設定檢查（必讀）

LINE Official Account Manager 設定路徑：
LINE Official Account Manager → 設定 → 回應設定

必要設定：
| 設定項目 | 正確值 | 說明 |
|----------|--------|------|
| Webhook | ✅ 開啟 | Bot 接收訊息的核心機制 |
| 自動回應訊息 | ❌ 關閉 | 必須關閉，否則每則訊息都會收到官方制式回覆 |
| AI 自動回應訊息 | ❌ 關閉 | 同上 |
| 智能聊天 | ❌ 關閉 | 同上 |
| 聊天 | 可選 | 開啟後可人工回覆，不影響 webhook |
| 歡迎訊息 | 可保留 | 只在使用者加好友時觸發，不干擾 webhook |

### Troubleshooting

**症狀：** 每次傳訊息都先收到「感謝您的訊息！很抱歉，本帳號無法個別回覆...」，然後才收到 bot 回覆。
**原因：** LINE OA 的「自動回應訊息」未關閉。這不是 webhook 程式錯誤。
**解決：** 到 LINE Official Account Manager → 設定 → 回應設定 → 自動回應訊息 → 關閉。

---

## 環境變數

| 變數 | 必要 | 說明 |
|------|------|------|
| LINE_CHANNEL_ACCESS_TOKEN | ✅ | LINE Developers Console → Messaging API → Channel access token |
| LINE_USER_ID | ✅ | 接收推播的使用者 LINE User ID |
| LINE_CHANNEL_SECRET | ✅ | LINE Developers Console → Basic settings → Channel secret（webhook 簽名驗證用） |
| PUBLIC_BASE_URL | 建議 | Web Dashboard 的公開 URL，例如 https://your-app.onrender.com |
| PYTHONIOENCODING | 建議 | 設為 utf-8，避免 Windows 中文顯示問題 |
| TZ | 建議 | 設為 Asia/Taipei，確保排程時間正確 |

---

## 部署 Checklist

- [ ] LINE OA 自動回應訊息已關閉
- [ ] Webhook URL 已設為 `https://<your-app>.onrender.com/webhook`
- [ ] Use webhook 已開啟
- [ ] Webhook redelivery 已開啟（建議，避免冷啟動時漏失訊息）
- [ ] Render 環境變數已設定（LINE_CHANNEL_ACCESS_TOKEN、LINE_USER_ID、LINE_CHANNEL_SECRET）
- [ ] `GET /health` 回傳 `{"status":"ok"}`

---

## 本地開發

```bash
# 建立 .env
cp .env.example .env
# 填入真實憑證後：
conda activate linebot
uvicorn app.main:app --reload --port 8000
```

使用 ngrok 或 Render 測試 webhook：
```bash
ngrok http 8000
# 將 https://<ngrok-url>/webhook 設為 LINE webhook URL
```
