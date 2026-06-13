# 台股智能推薦系統

每個交易日自動分析元大台灣50成分股，透過 LINE 推播技術面強勢股推薦。

## 功能

- 每日 14:00 CST 抓取 OHLCV 資料（yfinance）
- 計算技術指標：MA 交叉（5/20日）、RSI（14日）、MACD（12/26/9）
- 依綜合評分篩選技術面強勢股 / 轉弱警示
- 每日 08:30 CST 透過 LINE Messaging API 推播中文說明

## 環境需求

- conda 環境：`linebot`（Python 3.10）
- 已安裝：`line-bot-sdk 3.7.0`、`requests 2.31.0`、`yfinance`、`pandas`、`ta`、`apscheduler`

## 快速開始

1. 複製 `.env.example` 為 `.env`，填入 LINE 憑證：

```
LINE_CHANNEL_ACCESS_TOKEN=your_token
LINE_USER_ID=your_user_id
```

2. 驗證環境：

```bash
conda run -n linebot --no-capture-output python verify_live_send.py --full
```

3. 啟動排程：

```bash
conda run -n linebot --no-capture-output python scheduler.py
```

詳細部署說明請見 [docs/operator-guide.md](docs/operator-guide.md)。

## 檔案結構

| 檔案 | 說明 |
|------|------|
| `data_pipeline.py` | yfinance 資料抓取（0050成分股） |
| `analysis_engine.py` | 技術指標計算與評分 |
| `recommendation_generator.py` | 推薦選股與 LINE 訊息格式化 |
| `line_notifier.py` | LINE Messaging API 推播 |
| `scheduler.py` | APScheduler 排程（分析 + 推播） |
| `verify_live_send.py` | 端對端驗收測試 |
