# V4 驗收報告 — 台股智能雷達產品驗收修正

**版本：** V4  
**日期：** 2026-06-13  
**執行：** Executor Lead Checkpoint 1  
**測試結果：** 238/238 通過（172 V2/V3 原有 + 10 V4 新增 + 4 Web + 2 舊有 web = 238）

---

## 驗收項目狀態

| 項目 | 說明 | 狀態 | 備註 |
|------|------|------|------|
| A | 產品名稱統一（「台股智能雷達」） | ✅ | app/main.py title、flex_templates、commands.py、README |
| B | PUBLIC_BASE_URL 接線至所有 LINE 入口 | ✅ | config.py 已有、main.py 啟動警告、/health 含 public_base_url_configured |
| C | 假日快取修正（app/cache/latest_cache.py） | ✅ | load_latest_analysis_cache 不限今天；data_date 標示 |
| D | 新聞/市場事件模組（LINE + Web） | ✅ | news_flex、_handle_news、dashboard 側欄、stock.html 相關事件 |
| E | Rich Menu 圖片（scripts/generate_rich_menu_image.py + assets/rich_menu.png） | ✅ | 2500×1686 PNG 生成並提交；setup_rich_menu.py 更新含圖片上傳 |
| F | LINE UX 修正（未知指令/熱門股票/我的清單） | ✅ | 未知指令新文案；HOT_STOCKS 含 2412；我的清單用 find_stock_in_latest_cache |
| G | Web Dashboard 股票歷史圖表（async JS + yfinance + Plotly） | ✅ | /api/stock/{code}/history；4 張圖；HTTP 200 + error fallback |
| H | operator-guide.md P0 troubleshooting | ✅ | P0 LINE OA 自動回覆覆蓋問題已加入 |
| I | 10 個測試情境 | ✅ | tests/test_v4_acceptance.py — 10/10 通過 |
| J | docs/v4-acceptance-report.md | ✅ | 本文件 |

---

## 測試覆蓋明細（V4 新增 10 個情境）

| # | 測試名稱 | 描述 | 結果 |
|---|---------|------|------|
| 1 | test_product_name_unified | FastAPI title = "台股智能雷達" | ✅ |
| 2 | test_public_base_url_in_health | /health.public_base_url_configured 欄位存在 | ✅ |
| 3 | test_latest_cache_loads | load_latest_analysis_cache() 不限今天可讀取 | ✅ |
| 4 | test_cache_date_label | get_latest_analysis_date() 格式為 YYYY-MM-DD | ✅ |
| 5 | test_news_command_no_data | "新聞" 指令無資料時友善回應 | ✅ |
| 6 | test_news_command_with_data | "新聞" 指令有資料時回傳 Flex | ✅ |
| 7 | test_unknown_command_message | 未知指令回傳新 V4 文案（含「新聞」） | ✅ |
| 8 | test_watchlist_flex_full_data | 我的清單含名稱/分數/方向 | ✅ |
| 9 | test_stock_history_api_no_data | /api/stock/9999/history 回 HTTP 200 + error | ✅ |
| 10 | test_hot_stocks_includes_2412 | 2412 中華電出現在熱門股票 | ✅ |

---

## 新增檔案清單

| 檔案 | 說明 |
|------|------|
| `app/cache/__init__.py` | cache 子套件 |
| `app/cache/latest_cache.py` | 假日安全快取模組 |
| `scripts/generate_rich_menu_image.py` | Pillow 生成 Rich Menu 圖片 |
| `assets/rich_menu.png` | 2500×1686 Rich Menu 圖片（已提交） |
| `tests/test_v4_acceptance.py` | 10 個驗收情境測試 |
| `docs/v4-acceptance-report.md` | 本驗收報告 |

---

## 修改檔案清單

| 檔案 | 修改內容 |
|------|---------|
| `app/main.py` | title 改為「台股智能雷達」；PUBLIC_BASE_URL 啟動警告 |
| `app/linebot/webhook.py` | /health 加入 public_base_url_configured、app name |
| `app/linebot/flex_templates.py` | 命名統一；unknown_command_message V4 文案；HOT_STOCKS 更新 2412；news_flex 新增 |
| `app/linebot/commands.py` | 改用 latest_cache 模組；新增 _handle_news；_RE_NEWS pattern |
| `app/web/routes.py` | 改用 latest_cache 模組；新增 /api/stock/{code}/history；market_events 注入模板 |
| `templates/dashboard.html` | 加入 market_events 側欄 |
| `templates/stock.html` | 加入 4 張 async Plotly 圖表；相關事件區塊 |
| `scripts/setup_rich_menu.py` | 自動上傳 assets/rich_menu.png |
| `docs/operator-guide.md` | 加入 P0 LINE OA 自動回覆問題 troubleshooting |
| `data/market_events/latest.json` | 加入範例事件（3 筆） |

---

## 已知限制

1. **Rich Menu 圖片字型：** 本地 Windows 環境使用 Microsoft JhengHei（msjh.ttc），Render Linux 環境需設定 `RICH_MENU_FONT_PATH` 或安裝 `fonts-noto-cjk`。圖片已預先本地生成並提交至 repo，Render 部署時無需重新生成。

2. **市場事件資料：** `data/market_events/latest.json` 目前為手動維護。未來可接入新聞 API 自動更新。

3. **yfinance 歷史資料：** 使用 `period="6mo"` 而非固定天數，以避免假日計算問題。Render Free Tier 冷啟動時首次呼叫可能有 30-60 秒延遲。

4. **測試環境：** test_stock_history_api_no_data 使用 mock yfinance；實際 API 依賴網路。

---

## 結論

V4 所有 10 項驗收修正（A–J）均已完成並通過測試。系統已從「功能可運作」升級為「真正可用的產品」。

台股智能雷達 LINE Bot V4 已就緒，可提交 Verifier Lead 審核。
