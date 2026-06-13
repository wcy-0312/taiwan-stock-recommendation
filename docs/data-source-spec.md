# Data Source Spec

## 目前資料來源

| 資料類型 | 來源 | 更新頻率 | 備注 |
|----------|------|----------|------|
| OHLCV 行情 | yfinance（Yahoo Finance）| 每日 14:00 CST | .TW suffix（TWSE） |
| 股票池 | data/universes/tw0050.json | 手動維護 | 台灣 0050 成分股 50 支 |
| 新聞/事件 | data/market_events/latest.json | 手動維護 | 目前無自動抓取 |

## 限制

- 只支援 TWSE 上市股票（.TW suffix）
- 不支援 OTC（.TWO）
- 不支援即時/盤中資料
- 不支援法人籌碼（chip_score = None）
- yfinance 不保證資料完整性，以實際回傳為準

## 新聞/事件架構（目前為 fallback 模式）

新聞功能目前使用靜態 JSON fallback，沒有即時資料：
- `data/market_events/latest.json`：手動更新的市場事件
- 若未設定即時資料源，系統顯示「目前尚未接入即時新聞事件」

未來可接入的資料源（尚未實作）：
- 公開 RSS feed
- Yahoo Finance 新聞 API
- 財政部公告
