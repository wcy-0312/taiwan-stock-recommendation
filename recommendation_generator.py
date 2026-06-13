"""
ART-003: Recommendation Generator — WS-3
Selects the top 3–5 stocks from analysis_engine output and generates
plain-language Chinese explanations suitable for a LINE message.

Usage (standalone smoke test):
    conda run -n linebot python recommendation_generator.py
"""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from datetime import date
from typing import List, Optional

# ── Path setup — allow importing ART-001 and ART-002 from sibling dirs ─────────
_ARTIFACT_ROOT = os.path.join(os.path.dirname(__file__), "..", "..")
_ART001_PATH = os.path.join(_ARTIFACT_ROOT, "checkpoint-1", "ART-001")
_ART002_PATH = os.path.join(_ARTIFACT_ROOT, "checkpoint-1", "ART-002")
for _p in [_ART001_PATH, _ART002_PATH]:
    if _p not in sys.path:
        sys.path.insert(0, _p)


# ── Data class ─────────────────────────────────────────────────────────────────

@dataclass
class Recommendation:
    """A single stock recommendation with Chinese plain-language explanation."""
    ticker: str
    composite_score: int          # -3 to +3
    label: str                    # "BUY" | "SELL" | "HOLD"
    explanation_zh: str           # Chinese plain-language explanation
    latest_close: Optional[float] = None


# ── Explanation helpers ────────────────────────────────────────────────────────

# Ticker → Chinese company name lookup (subset of 0050 universe)
_TICKER_NAMES: dict[str, str] = {
    "2330.TW": "台積電",
    "2454.TW": "聯發科",
    "2317.TW": "鴻海",
    "2308.TW": "台達電",
    "2882.TW": "國泰金",
    "2881.TW": "富邦金",
    "2303.TW": "聯電",
    "1301.TW": "台塑",
    "1303.TW": "南亞",
    "2412.TW": "中華電",
    "2002.TW": "中鋼",
    "1326.TW": "台化",
    "2886.TW": "兆豐金",
    "2884.TW": "玉山金",
    "3711.TW": "日月光投控",
    "2891.TW": "中信金",
    "2892.TW": "第一金",
    "5880.TW": "合庫金",
    "2885.TW": "元大金",
    "2880.TW": "華南金",
    "2883.TW": "開發金",
    "2887.TW": "台新金",
    "2888.TW": "新光金",
    "2890.TW": "永豐金",
    "2801.TW": "彰銀",
    "1402.TW": "遠東新",
    "2207.TW": "和泰車",
    "2382.TW": "廣達",
    "2395.TW": "研華",
    "4938.TW": "和碩",
    "2357.TW": "華碩",
    "2379.TW": "瑞昱",
    "3034.TW": "聯詠",
    "2327.TW": "國巨",
    "2301.TW": "光寶科",
    "6505.TW": "台塑化",
    "2353.TW": "宏碁",
    "2352.TW": "仁寶",
    "2356.TW": "英業達",
    "3008.TW": "大立光",
    "2376.TW": "技嘉",
    "2385.TW": "群光",
    "2408.TW": "南亞科",
    "3006.TW": "晶豪科",
    "2474.TW": "可成",
    "2603.TW": "長榮",
    "2615.TW": "萬海",
    "2609.TW": "陽明",
    "2610.TW": "華航",
    "2618.TW": "長榮航",
}


def _ticker_display(ticker: str) -> str:
    """Return 'NNNN 公司名' display string."""
    code = ticker.replace(".TW", "")
    name = _TICKER_NAMES.get(ticker, "")
    return f"{code} {name}".strip()


def _signal_sentence_zh(strategy: str, signal: str, detail: str) -> str:
    """
    Produce one Chinese sentence summarising a strategy signal.
    Keeps language jargon-free for a non-expert audience.
    """
    if strategy == "MA_CROSSOVER":
        if signal == "BUY":
            return "近期股價的短線平均成本已高於長線平均成本，顯示買盤逐漸增溫。"
        elif signal == "SELL":
            return "近期股價的短線平均成本已低於長線平均成本，顯示賣壓相對較大。"
        else:
            return "短線與長線平均成本相近，目前方向不明確。"
    elif strategy == "RSI":
        if signal == "BUY":
            return "股價最近跌得較多，根據動能指標已進入「超賣」區域，可能出現反彈機會。"
        elif signal == "SELL":
            return "股價最近漲得較多，根據動能指標已進入「超買」區域，可能面臨獲利了結賣壓。"
        else:
            return "動能指標處於中性區間，目前沒有明顯的超買或超賣訊號。"
    elif strategy == "MACD":
        if signal == "BUY":
            return "均線動能指標（MACD）顯示上升力道正在增強，短線偏多。"
        elif signal == "SELL":
            return "均線動能指標（MACD）顯示下跌力道正在增強，短線偏空。"
        else:
            return "均線動能指標（MACD）目前處於中性，動能方向尚未確立。"
    return ""


def _build_explanation(analysis) -> str:
    """
    Build a multi-line Chinese plain-language explanation from a StockAnalysis object.
    """
    display = _ticker_display(analysis.ticker)
    label_zh = {"BUY": "建議買入", "SELL": "建議賣出", "HOLD": "建議觀望"}.get(
        analysis.recommendation, "建議觀望"
    )

    lines = [f"【{display}】{label_zh}（綜合分數：{analysis.composite_score:+d}）"]

    if analysis.latest_close is not None:
        lines.append(f"最新收盤價：{analysis.latest_close:.2f} 元")

    for sig in (analysis.signals or []):
        sentence = _signal_sentence_zh(sig.strategy, sig.signal, sig.detail)
        if sentence:
            lines.append(f"▸ {sentence}")

    return "\n".join(lines)


# ── Core selection logic ───────────────────────────────────────────────────────

def select_top_recommendations(
    analyses: list,
    top_n_buy: int = 3,
    top_n_sell: int = 2,
    min_abs_score: int = 1,
) -> List[Recommendation]:
    """
    Select the top 3–5 stocks to highlight.

    Strategy:
    - Take up to `top_n_buy` stocks with the highest positive composite scores
    - Take up to `top_n_sell` stocks with the lowest (most negative) scores
    - Skip stocks with abs(composite_score) < min_abs_score (pure HOLD)
    - Total capped at 5 recommendations; minimum 3 if universe is small

    Parameters
    ----------
    analyses      : list of StockAnalysis (sorted desc by composite_score)
    top_n_buy     : max BUY recommendations to include
    top_n_sell    : max SELL recommendations to include
    min_abs_score : ignore stocks whose abs(score) is below this threshold

    Returns
    -------
    List[Recommendation] — 3 to 5 items, BUYs first then SELLs
    """
    valid = [a for a in analyses if not getattr(a, "error", None)]

    # BUY candidates: highest positive scores
    buy_candidates = [a for a in valid if a.composite_score > 0]
    buy_candidates.sort(key=lambda a: a.composite_score, reverse=True)
    selected_buy = buy_candidates[:top_n_buy]

    # SELL candidates: most negative scores
    sell_candidates = [a for a in valid if a.composite_score < 0]
    sell_candidates.sort(key=lambda a: a.composite_score)  # ascending (most negative first)
    selected_sell = sell_candidates[:top_n_sell]

    # If total < 3, fill with best HOLD stocks (score == 0, sorted by ticker)
    selected = selected_buy + selected_sell
    if len(selected) < 3:
        hold_candidates = [
            a for a in valid
            if a not in selected_buy and a not in selected_sell
        ]
        hold_candidates.sort(key=lambda a: a.ticker)
        needed = 3 - len(selected)
        selected += hold_candidates[:needed]

    # Build Recommendation objects
    recommendations: List[Recommendation] = []
    for analysis in selected:
        explanation = _build_explanation(analysis)
        rec = Recommendation(
            ticker=analysis.ticker,
            composite_score=analysis.composite_score,
            label=analysis.recommendation,
            explanation_zh=explanation,
            latest_close=analysis.latest_close,
        )
        recommendations.append(rec)

    return recommendations


# ── LINE message formatter ─────────────────────────────────────────────────────

def format_line_message(recommendations: List[Recommendation], run_date: Optional[str] = None) -> str:
    """
    Format the full LINE push message from a list of Recommendation objects.

    Parameters
    ----------
    recommendations : list of Recommendation
    run_date        : date string (YYYY-MM-DD); defaults to today

    Returns
    -------
    str — plain-text LINE message (no markdown, uses unicode symbols)
    """
    if run_date is None:
        run_date = date.today().isoformat()

    header = (
        f"📊 台股每日推薦 {run_date}\n"
        f"{'─' * 28}\n"
        f"以下為今日技術分析結果，供參考，非投資建議。\n"
    )

    sections: list[str] = []
    for i, rec in enumerate(recommendations, start=1):
        sections.append(rec.explanation_zh)

    footer = (
        "\n📌 提醒：以上分析僅基於技術指標，不保證獲利。\n"
        "投資人請自行判斷，風險自負。"
    )

    body = f"\n{'─' * 28}\n".join(sections)
    return f"{header}\n{body}{footer}"


# ── Public pipeline entry point ────────────────────────────────────────────────

def generate_recommendations(
    analyses: list,
    top_n_buy: int = 3,
    top_n_sell: int = 2,
    run_date: Optional[str] = None,
) -> tuple[List[Recommendation], str]:
    """
    Full pipeline: select top stocks → generate Chinese explanations → format LINE message.

    Parameters
    ----------
    analyses   : list of StockAnalysis from analysis_engine.analyse_universe()
    top_n_buy  : max BUY picks
    top_n_sell : max SELL picks
    run_date   : date string for the message header

    Returns
    -------
    (recommendations, line_message_text)
    """
    recommendations = select_top_recommendations(analyses, top_n_buy, top_n_sell)
    message = format_line_message(recommendations, run_date)
    return recommendations, message


# ── Smoke test ────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("=== recommendation_generator smoke test ===\n")

    # Import upstream modules
    try:
        from data_pipeline import fetch_universe, TAIWAN_0050_TICKERS
        from analysis_engine import analyse_universe
    except ImportError as e:
        print(f"[ERROR] Cannot import upstream module: {e}")
        print("Make sure ART-001 and ART-002 are on sys.path.")
        sys.exit(1)

    # Fetch a small sample universe for speed
    SAMPLE = TAIWAN_0050_TICKERS[:10]
    print(f"Fetching data for {len(SAMPLE)} tickers...")
    data = fetch_universe(tickers=SAMPLE, days=60)

    if not data:
        print("[FAIL] No data returned from data_pipeline")
        sys.exit(1)

    print(f"Got data for {len(data)} tickers. Running analysis...")
    analyses = analyse_universe(data)

    recommendations, message = generate_recommendations(analyses)

    print(f"\nSelected {len(recommendations)} recommendation(s):\n")
    for rec in recommendations:
        print(f"  {rec.ticker}: {rec.label} (score={rec.composite_score:+d})")

    print("\n" + "=" * 50)
    print("LINE MESSAGE PREVIEW:")
    print("=" * 50)
    print(message)
    print("=" * 50)

    assert 3 <= len(recommendations) <= 5, (
        f"Expected 3–5 recommendations, got {len(recommendations)}"
    )
    for rec in recommendations:
        assert rec.ticker, "Ticker must not be empty"
        assert rec.label in ("BUY", "SELL", "HOLD"), f"Invalid label: {rec.label}"
        assert rec.explanation_zh, "Chinese explanation must not be empty"

    print("\n[PASS] recommendation_generator smoke test complete")
