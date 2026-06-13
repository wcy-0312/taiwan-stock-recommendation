"""
scripts/setup_rich_menu.py — Create and set the LINE Bot Rich Menu.

Usage:
    python scripts/setup_rich_menu.py [--delete-all]

Requires:
    LINE_CHANNEL_ACCESS_TOKEN in environment or .env file
    PUBLIC_BASE_URL in environment or .env file  (REQUIRED — exits if missing)

Rich Menu layout (6-grid, 2×3):
    Row 1: 今日雷達 (uri) | 強勢排行 (uri) | 風險警示 (uri)
    Row 2: 查詢個股 (uri) | 我的追蹤 (message) | 市場事件 (uri)
"""
import argparse
import json
import os
import sys
import urllib.request
import urllib.error
from pathlib import Path


def _load_dotenv():
    env_path = Path(__file__).parent.parent / ".env"
    if env_path.exists():
        with env_path.open() as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, _, v = line.partition("=")
                    os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


def _api(method, path, body=None):
    token = os.environ.get("LINE_CHANNEL_ACCESS_TOKEN", "")
    url = f"https://api.line.me{path}"
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    data = json.dumps(body, ensure_ascii=False).encode() if body else None
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as e:
        err = e.read().decode()
        print(f"[ERROR] {method} {path}: HTTP {e.code} — {err}")
        raise


def create_rich_menu(base_url: str) -> str:
    """Build Rich Menu with URI actions where possible.

    Grid layout (x, y, width, height):
        Row 0 (top):    y=0,    height=843
        Row 1 (bottom): y=843,  height=843
        Col 0 (left):   x=0,    width=833
        Col 1 (mid):    x=833,  width=833
        Col 2 (right):  x=1666, width=834
    """
    b = base_url.rstrip("/")

    rich_menu = {
        "size": {"width": 2500, "height": 1686},
        "selected": True,
        "name": "台股智能雷達 主選單 v2",
        "chatBarText": "📊 開啟選單",
        "areas": [
            # 今日雷達 — URI: /dashboard
            {
                "bounds": {"x": 0, "y": 0, "width": 833, "height": 843},
                "action": {"type": "uri", "uri": f"{b}/dashboard"},
            },
            # 強勢排行 — URI: /dashboard?tab=strong
            {
                "bounds": {"x": 833, "y": 0, "width": 833, "height": 843},
                "action": {"type": "uri", "uri": f"{b}/dashboard?tab=strong"},
            },
            # 風險警示 — URI: /dashboard?tab=weak
            {
                "bounds": {"x": 1666, "y": 0, "width": 834, "height": 843},
                "action": {"type": "uri", "uri": f"{b}/dashboard?tab=weak"},
            },
            # 查詢個股 — URI: /search
            {
                "bounds": {"x": 0, "y": 843, "width": 833, "height": 843},
                "action": {"type": "uri", "uri": f"{b}/search"},
            },
            # 我的追蹤 — message: Bot generates personalized token link
            # Web view requires a short-lived token that only the Bot can issue.
            {
                "bounds": {"x": 833, "y": 843, "width": 833, "height": 843},
                "action": {"type": "message", "text": "我的清單"},
            },
            # 市場事件 — URI: /dashboard#events
            {
                "bounds": {"x": 1666, "y": 843, "width": 834, "height": 843},
                "action": {"type": "uri", "uri": f"{b}/dashboard#events"},
            },
        ],
    }

    result = _api("POST", "/v2/bot/richmenu", rich_menu)
    rich_menu_id = result["richMenuId"]
    print(f"[OK] Created Rich Menu: {rich_menu_id}")

    image_path = Path(__file__).parent.parent / "assets" / "rich_menu.png"
    if image_path.exists():
        _upload_rich_menu_image(rich_menu_id, image_path)
    else:
        print("[WARN] assets/rich_menu.png not found — skipping image upload.")
        print("       Run: python scripts/generate_rich_menu_image.py")

    _api("POST", f"/v2/bot/user/all/richmenu/{rich_menu_id}")
    print("[OK] Set as default Rich Menu")
    return rich_menu_id


def _upload_rich_menu_image(rich_menu_id: str, image_path: Path) -> None:
    token = os.environ.get("LINE_CHANNEL_ACCESS_TOKEN", "")
    url = f"https://api-data.line.me/v2/bot/richmenu/{rich_menu_id}/content"
    with image_path.open("rb") as f:
        image_data = f.read()
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "image/png"}
    req = urllib.request.Request(url, data=image_data, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req) as resp:
            resp.read()
        print(f"[OK] Uploaded Rich Menu image: {image_path.name}")
    except urllib.error.HTTPError as e:
        err = e.read().decode()
        print(f"[ERROR] Image upload failed: HTTP {e.code} — {err}")


def delete_all_rich_menus():
    result = _api("GET", "/v2/bot/richmenu/list")
    menus = result.get("richmenus", [])
    if not menus:
        print("[INFO] No rich menus found.")
        return
    for m in menus:
        rid = m["richMenuId"]
        _api("DELETE", f"/v2/bot/richmenu/{rid}")
        print(f"[OK] Deleted {rid}")


def main():
    _load_dotenv()

    parser = argparse.ArgumentParser(description="Set up LINE Bot Rich Menu")
    parser.add_argument("--delete-all", action="store_true", help="Delete all existing rich menus first")
    parsed = parser.parse_args()

    # Fail-fast: PUBLIC_BASE_URL is required for URI actions
    base_url = os.environ.get("PUBLIC_BASE_URL", "").rstrip("/")
    if not base_url:
        print("[ERROR] PUBLIC_BASE_URL is not set.")
        print("        Rich Menu uses URI actions that require an absolute base URL.")
        print("        Set PUBLIC_BASE_URL in your .env or shell environment, e.g.:")
        print("          export PUBLIC_BASE_URL=https://your-app.onrender.com")
        print("        Aborting — no Rich Menu was created.")
        sys.exit(1)

    token = os.environ.get("LINE_CHANNEL_ACCESS_TOKEN", "")
    if not token:
        print("[ERROR] LINE_CHANNEL_ACCESS_TOKEN is not set. Aborting.")
        sys.exit(1)

    if parsed.delete_all:
        print("Deleting existing rich menus...")
        delete_all_rich_menus()

    print(f"Creating Rich Menu with base URL: {base_url}")
    create_rich_menu(base_url)


if __name__ == "__main__":
    main()
