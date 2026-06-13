# Product Spec — 台股智能雷達 LINE Bot V3

## 產品定位

量化技術觀察工具，非投資建議。幫助使用者快速了解 0050 成分股的技術面狀態。

## 架構

```
LINE Bot ←→ FastAPI (Render Web Service)
                ├── Webhook Handler
                ├── APScheduler（分析 14:00 / 推播 08:30 CST）
                ├── Web Dashboard (/dashboard, /stock/{code})
                └── REST API (/api/radar/latest, /api/stock/{code})
```

## 功能

### LINE Bot
- 每日自動推播（强勢觀察、轉弱警示、市場摘要）
- 個股查詢（radar_score、5大分項、正負面訊號）
- 追蹤清單（SQLite 持久化）
- Quick Reply 互動按鈕
- 親切的問候和引導體驗

### Web Dashboard
- 今日雷達總覽（/dashboard）
- 個股詳細頁（/stock/{code}）含 Plotly 圖表
- REST API 供外部查詢

## 評分系統

見 docs/scoring-spec.md

## 推薦分類

| 分類 | 條件 |
|------|------|
| 強勢延續 | 高分、趨勢穩、量能正常、風險低 |
| 剛轉強 | MACD 翻正、站回 MA20、量增 |
| 過熱勿追 | 高分但 RSI > 75 或接近壓力 |
| 轉弱警示 | 低分、跌破 MA20、MACD 翻負 |
| 觀望整理 | 中性分數、訊號混雜 |
