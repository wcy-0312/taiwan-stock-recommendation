"""
scripts/setup_rich_menu.py — Create and set the LINE Bot Rich Menu.

Usage:
    python scripts/setup_rich_menu.py [--delete-all]

Requires:
    LINE_CHANNEL_ACCESS_TOKEN in environment or .env file
    Optional: PUBLIC_BASE_URL for dashboard link
"""
import argparse
import json
import os
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

def create_rich_menu(base_url=""):
    dashboard_url = f"{base_url}/dashboard" if base_url else "https://line.me"
    rich_menu = {
        "size": {"width": 2500, "height": 1686},
        "selected": True,
        "name": "台股智能雷達 主選單",
        "chatBarText": "📊 開啟選單",
        "areas": [
            {"bounds": {"x":0,"y":0,"width":833,"height":843},
             "action": {"type":"message","text":"今日雷達"}},
            {"bounds": {"x":833,"y":0,"width":833,"height":843},
             "action": {"type":"message","text":"強勢股"}},
            {"bounds": {"x":1666,"y":0,"width":834,"height":843},
             "action": {"type":"message","text":"轉弱股"}},
            {"bounds": {"x":0,"y":843,"width":833,"height":843},
             "action": {"type":"message","text":"查 "}},
            {"bounds": {"x":833,"y":843,"width":833,"height":843},
             "action": {"type":"message","text":"我的清單"}},
            {"bounds": {"x":1666,"y":843,"width":834,"height":843},
             "action": {"type":"uri","uri": dashboard_url}},
        ]
    }
    result = _api("POST", "/v2/bot/richmenu", rich_menu)
    rich_menu_id = result["richMenuId"]
    print(f"[OK] Created Rich Menu: {rich_menu_id}")
    # Set as default
    _api("POST", f"/v2/bot/user/all/richmenu/{rich_menu_id}")
    print(f"[OK] Set as default Rich Menu")
    print()
    print("NOTE: You still need to upload a Rich Menu image (2500x1686px) via:")
    print(f"  POST https://api-data.line.me/v2/bot/richmenu/{rich_menu_id}/content")
    print("  Content-Type: image/png or image/jpeg")
    return rich_menu_id

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
    args = parser.parse_args()
    base_url = os.environ.get("PUBLIC_BASE_URL", "").rstrip("/")
    if args.delete_all:
        print("Deleting existing rich menus...")
        delete_all_rich_menus()
    print("Creating Rich Menu...")
    create_rich_menu(base_url)

if __name__ == "__main__":
    main()
