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
| 中下 | 📋 我的追蹤 | **message** | `我的清單` | 暫時保留 message，見下方說明 |
| 右下 | 📰 市場事件 | **uri** | `{PUBLIC_BASE_URL}/dashboard#events` | 市場事件側欄 |

**URI 格數：5 / 6　　Message 格數：1 / 6**

---

## 為什麼「我的追蹤」暫時保留 message？

**現況：** 我的清單（watchlist）儲存在 SQLite，以 LINE user_id 為 key。  
**限制：** Web 端無法可靠知道瀏覽者的 LINE user_id（需 LIFF SDK + 登入授權）。  
**中期目標：** 接入 LIFF，讓 Web 頁面 `/watchlist` 能透過 `liff.getProfile()` 取得 user_id，改為 uri action `{PUBLIC_BASE_URL}/watchlist`。  
**目前：** 點擊後送出文字「我的清單」，Bot 回覆清單（LINE 內完成，不依賴 Web）。

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

## 中期路線圖

| 格 | 現在 | 中期 |
|----|------|------|
| 我的追蹤 | message: 我的清單 | uri: `{PUBLIC_BASE_URL}/watchlist`（需 LIFF） |
