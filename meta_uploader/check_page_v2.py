import json
import os
from pathlib import Path

import requests

try:
    from dotenv import load_dotenv
except ImportError:
    load_dotenv = None


BASE_DIR = Path(__file__).resolve().parent


def _strip_quotes(value):
    return value.strip().strip('"').strip("'")


def load_local_env():
    if load_dotenv:
        load_dotenv(BASE_DIR / ".env")

    env_path = BASE_DIR / ".env"
    if not env_path.exists():
        return

    with open(env_path, "r", encoding="utf-8") as handle:
        for raw_line in handle:
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            if key and key not in os.environ:
                os.environ[key.strip()] = _strip_quotes(value)


def pretty_print(title, payload):
    print(f"\n[{title}]")
    print(json.dumps(payload, indent=2, ensure_ascii=False))


def check_page_status():
    load_local_env()
    api_version = os.environ.get("META_GRAPH_API_VERSION", "v19.0").strip() or "v19.0"
    token = os.environ.get("META_FB_PAGE_TOKEN", "") or os.environ.get("META_PAGE_TOKEN", "")
    page_id = os.environ.get("META_FB_PAGE_ID", "")

    if not token or not page_id:
        print("Faltan META_FB_PAGE_ID y/o token para consultar la pagina.")
        return

    print(f"Verificando acceso a la pagina {page_id} usando Graph API {api_version}...")
    page_url = f"https://graph.facebook.com/{api_version}/{page_id}"
    page_info = requests.get(
        page_url,
        params={
            "access_token": token,
            "fields": "name,is_published,verification_status",
        },
        timeout=60,
    ).json()
    pretty_print("page", page_info)

    videos_url = f"https://graph.facebook.com/{api_version}/{page_id}/videos"
    videos_info = requests.get(
        videos_url,
        params={"access_token": token, "limit": 1},
        timeout=60,
    ).json()
    pretty_print("videos", videos_info)


if __name__ == "__main__":
    check_page_status()
