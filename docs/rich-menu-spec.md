# Rich Menu Spec

## 佈局：6 宮格（2 行 × 3 欄）

| 位置 | 標籤 | 動作類型 | 動作內容 |
|------|------|----------|----------|
| 左上 | 📊 今日雷達 | message | 今日雷達 |
| 中上 | 🏆 強勢觀察 | message | 強勢股 |
| 右上 | ⚠️ 轉弱警示 | message | 轉弱股 |
| 左下 | 🔍 查詢個股 | message | 查 |
| 中下 | 📋 我的清單 | message | 我的清單 |
| 右下 | 🌐 完整看板 | uri | https://taiwan-stock-radar-linebot.onrender.com/dashboard |

## Rich Menu 尺寸規格

- 寬度：2500px
- 高度：1686px（全尺寸）或 843px（半尺寸）
- 每格寬度：833px
- 每格高度：843px（全尺寸）

## 建立方式

執行 `python scripts/setup_rich_menu.py` 自動建立並設定 Rich Menu。
需要 LINE_CHANNEL_ACCESS_TOKEN 環境變數。

## 手動建立步驟

1. 準備 2500×1686px 的 Rich Menu 圖片
2. 在 LINE Official Account Manager → Rich menu 新增
3. 按上表設定每格動作
4. 發布並設為預設
