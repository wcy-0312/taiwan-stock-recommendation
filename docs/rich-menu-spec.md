# Rich Menu Spec

> 版本：v2（2026-06-13）
> 設計原則：LINE Rich Menu 是入口，不是聊天指令快捷鍵。能在 Web 完成的操作直接跳 Web。

---

## 6 格動作一覽

| 格 | 標籤 | action | URI / 文字 | 備註 |
|----|------|--------|-----------|------|
| 左上 | 📊 今日雷達 | **uri** | `{PUBLIC_BASE_URL}/dashboard` | 完整雷達看板 |
| 中上 | 🏆 強勢排行 | **uri** | `{PUBLIC_BASE_URL}/dashboard?tab=strong` | 強勢股排行 |
| 右上 | ⚠️ 風險警示 | **uri** | `{PUBLIC_BASE_URL}/dashboard?tab=weak` | 轉弱警示 |
| 左下 | 🔍 查詢個股 | **uri** | `{PUBLIC_BASE_URL}/search` | 搜尋頁（支援輸入代號） |
| 中下 | 📋 我的追蹤 | **message** | `我的清單` | Bot 產生 token 連結後跳 Web |
| 右下 | 📰 市場事件 | **uri** | `{PUBLIC_BASE_URL}/dashboard#events` | 市場事件側欄 |

**URI 格數：5 / 6　　Message 格數：1 / 6**

---

## 「我的追蹤」— Token 連結機制

LIFF 在 2024 年已不可加入 Messaging API Channel，改用 **Bot 發放 token 連結**的方式：

**使用者流程：**
1. 點 Rich Menu「我的追蹤」→ 傳送「我的清單」給 Bot
2. Bot 查詢清單、產生 30 分鐘有效 token
3. Bot 回傳 Flex Message（含個股清單）+ 「開啟追蹤清單」按鈕
4. 點按鈕 → 瀏覽器開啟 `/watchlist?token=xxx` → Web 個人清單頁

**優點：** 不需要 LIFF、LINE Login Channel、或任何帳號連結，token 由 Bot 在 server 端驗證。

**Token 特性：**
- 格式：URL-safe 隨機 16 bytes（`secrets.token_urlsafe(16)`）
- TTL：30 分鐘（過期自動失效）
- 儲存：process in-memory（Render 重啟後失效，使用者重新輸入「我的清單」即可）

---

## 尺寸規格

- 圖片：2500 × 1686 px（全尺寸，2 行 × 3 欄）
- 每格（Col 0/1）：833 × 843 px
- 每格（Col 2）：834 × 843 px（最右欄加 1px 補足 2500）

---

## 建立流程

```bash
# Step 1：生成圖片（本機執行，需 Pillow + CJK 字型）
python scripts/generate_rich_menu_image.py
# → assets/rich_menu.png

# Step 2：上傳並設為預設（需 LINE_CHANNEL_ACCESS_TOKEN + PUBLIC_BASE_URL）
python scripts/setup_rich_menu.py [--delete-all]
```

**注意：** `setup_rich_menu.py` 若未設定 `PUBLIC_BASE_URL` 會**直接報錯停止**，不 fallback 到任何 URL。

---

## 環境變數

| 變數 | 必要 | 說明 |
|------|------|------|
| `LINE_CHANNEL_ACCESS_TOKEN` | ✅ | 上傳/建立 Rich Menu 用 |
| `PUBLIC_BASE_URL` | ✅ | URI action 的 base URL，例如 `https://your-app.onrender.com` |
| `RICH_MENU_FONT_PATH` | 選用 | 指定 CJK 字型路徑，否則依序搜尋系統字型 |

---

## 環境變數

| 變數 | 必要 | 說明 |
|------|------|------|
| `LINE_CHANNEL_ACCESS_TOKEN` | ✅ | 上傳/建立 Rich Menu 用 |
| `PUBLIC_BASE_URL` | ✅ | URI action base URL |
| `LIFF_ID` | ✅（我的追蹤） | LIFF App ID，格式 `1234567890-xxxxxxxx` |
| `RICH_MENU_FONT_PATH` | 選用 | CJK 字型路徑（否則搜尋系統字型） |
