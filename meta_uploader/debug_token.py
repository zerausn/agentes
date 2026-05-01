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


def debug_meta_token():
    load_local_env()
    api_version = os.environ.get("META_GRAPH_API_VERSION", "v19.0").strip() or "v19.0"
    token = (
        os.environ.get("META_IG_USER_TOKEN", "")
        or os.environ.get("META_FB_PAGE_TOKEN", "")
        or os.environ.get("META_PAGE_TOKEN", "")
    )

    if not token:
        print("No se encontro ningun token de Meta en .env.")
        return

    print("Depurando token actual con Meta...")
    debug_response = requests.get(
        "https://graph.facebook.com/debug_token",
        params={"input_token": token, "access_token": token},
        timeout=60,
    ).json()
    print(json.dumps(debug_response, indent=2, ensure_ascii=False))

    permissions_response = requests.get(
        f"https://graph.facebook.com/{api_version}/me/permissions",
        params={"access_token": token},
        timeout=60,
    ).json()
    print("\nPermisos visibles para el token:")
    print(json.dumps(permissions_response, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    debug_meta_token()
