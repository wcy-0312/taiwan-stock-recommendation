"""
scripts/generate_rich_menu_image.py — Generate Rich Menu image using Pillow.

Produces a 2500×1686 PNG with 6 cells (2 rows × 3 cols):
    Row 1: 今日雷達 | 強勢排行 | 風險警示
    Row 2: 查詢個股  | 我的追蹤 | 市場事件

Font search order:
    1. RICH_MENU_FONT_PATH env var
    2. Windows JhengHei
    3. macOS PingFang SC
    4. Linux NotoSansCJK
    5. PIL default (no CJK — warns user)

Usage:
    python scripts/generate_rich_menu_image.py [--output assets/rich_menu.png]
"""
from __future__ import annotations

import argparse
import logging
import os
import sys
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

# ── Layout constants ──────────────────────────────────────────────────────────
IMG_W = 2500
IMG_H = 1686
COLS = 3
ROWS = 2
CELL_W = IMG_W // COLS     # 833
CELL_H = IMG_H // ROWS     # 843

CELLS = [
    # (row, col, emoji, label, hint)   hint = action-type label shown in image
    (0, 0, "📊", "今日雷達", "Web ↗"),
    (0, 1, "🏆", "強勢排行", "Web ↗"),
    (0, 2, "⚠️", "風險警示", "Web ↗"),
    (1, 0, "🔍", "查詢個股", "Web ↗"),
    (1, 1, "📋", "我的追蹤", "訊息"),
    (1, 2, "📰", "市場事件", "Web ↗"),
]

# Background & text colours
BG_COLOR = (26, 29, 46)          # dark navy
CELL_BORDER_COLOR = (45, 55, 72) # subtle border
EMOJI_COLOR = (99, 179, 237)     # light blue
LABEL_COLOR = (226, 232, 240)    # near white
HINT_COLOR = (113, 128, 150)     # grey hint


def _find_font(size: int):
    """Return (ImageFont, had_cjk) — had_cjk is False if fell back to default."""
    from PIL import ImageFont

    # 1. Env override
    env_path = os.environ.get("RICH_MENU_FONT_PATH", "")
    if env_path and Path(env_path).exists():
        try:
            return ImageFont.truetype(env_path, size), True
        except Exception:
            pass

    # 2. Platform candidates
    candidates = [
        # Windows
        r"C:\Windows\Fonts\msjh.ttc",       # Microsoft JhengHei
        r"C:\Windows\Fonts\msjhbd.ttc",
        r"C:\Windows\Fonts\mingliu.ttc",
        # macOS
        "/System/Library/Fonts/PingFang.ttc",
        "/System/Library/Fonts/STHeiti Light.ttc",
        # Linux (apt: fonts-noto-cjk)
        "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/noto-cjk/NotoSansCJKtc-Regular.otf",
    ]
    for path in candidates:
        if Path(path).exists():
            try:
                return ImageFont.truetype(path, size), True
            except Exception:
                continue

    # 3. Fallback — no CJK
    logger.warning(
        "找不到中文字型，可能導致中文顯示為方框。"
        "建議設定 RICH_MENU_FONT_PATH 環境變數指向 TTF/TTC 字型檔。"
    )
    return ImageFont.load_default(), False


def generate(output_path: Path) -> None:
    """Generate the rich menu PNG and save to output_path."""
    try:
        from PIL import Image, ImageDraw
    except ImportError:
        logger.error("Pillow not installed. Run: pip install Pillow")
        sys.exit(1)

    img = Image.new("RGB", (IMG_W, IMG_H), BG_COLOR)
    draw = ImageDraw.Draw(img)

    # Fonts
    font_emoji, _ = _find_font(160)
    font_label, had_cjk = _find_font(100)
    font_hint, _ = _find_font(60)

    if not had_cjk:
        logger.warning("使用 PIL 預設字型，中文字元可能無法正常顯示。")

    for row, col, emoji, label, hint in CELLS:
        x0 = col * CELL_W
        y0 = row * CELL_H
        x1 = x0 + CELL_W
        y1 = y0 + CELL_H

        # Cell border (draw rectangle outline)
        draw.rectangle([x0, y0, x1 - 1, y1 - 1], outline=CELL_BORDER_COLOR, width=3)

        # Emoji (centred horizontally, upper third)
        cx = x0 + CELL_W // 2
        emoji_y = y0 + CELL_H // 4

        # PIL ImageFont doesn't have getbbox before Pillow 9; use textlength for centering
        try:
            eb = draw.textbbox((0, 0), emoji, font=font_emoji)
            ew = eb[2] - eb[0]
        except AttributeError:
            ew = 0
        draw.text((cx - ew // 2, emoji_y), emoji, font=font_emoji, fill=EMOJI_COLOR)

        # Label
        label_y = y0 + CELL_H // 2 - 20
        try:
            lb = draw.textbbox((0, 0), label, font=font_label)
            lw = lb[2] - lb[0]
        except AttributeError:
            lw = 0
        draw.text((cx - lw // 2, label_y), label, font=font_label, fill=LABEL_COLOR)

        # Hint (command text)
        hint_y = label_y + 120
        try:
            hb = draw.textbbox((0, 0), hint, font=font_hint)
            hw = hb[2] - hb[0]
        except AttributeError:
            hw = 0
        draw.text((cx - hw // 2, hint_y), hint, font=font_hint, fill=HINT_COLOR)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    img.save(str(output_path), "PNG")
    logger.info("Rich Menu image saved: %s (%dx%d)", output_path, IMG_W, IMG_H)


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate Rich Menu image")
    parser.add_argument(
        "--output",
        default="assets/rich_menu.png",
        help="Output path for the PNG (default: assets/rich_menu.png)",
    )
    args = parser.parse_args()

    # Resolve relative to project root (parent of scripts/)
    output_path = Path(args.output)
    if not output_path.is_absolute():
        project_root = Path(__file__).parent.parent
        output_path = project_root / output_path

    generate(output_path)


if __name__ == "__main__":
    main()
