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


def save_page_token(new_token):
    env_path = BASE_DIR / ".env"
    existing_lines = env_path.read_text(encoding="utf-8").splitlines() if env_path.exists() else []
    updated_lines = []
    replaced = False

    for line in existing_lines:
        if line.startswith("META_FB_PAGE_TOKEN="):
            updated_lines.append(f"META_FB_PAGE_TOKEN={new_token}")
            replaced = True
        else:
            updated_lines.append(line)

    if not replaced:
        updated_lines.append(f"META_FB_PAGE_TOKEN={new_token}")

    env_path.write_text("\n".join(updated_lines) + "\n", encoding="utf-8")


def get_page_token():
    load_local_env()
    api_version = os.environ.get("META_GRAPH_API_VERSION", "v19.0").strip() or "v19.0"
    bootstrap_token = os.environ.get("META_PAGE_TOKEN", "")
    page_id = os.environ.get("META_FB_PAGE_ID", "")

    if not bootstrap_token or not page_id:
        print("Faltan META_PAGE_TOKEN o META_FB_PAGE_ID en .env.")
        return

    print("Solicitando Page Access Token a Meta...")
    response = requests.get(
        f"https://graph.facebook.com/{api_version}/{page_id}",
        params={"fields": "name,access_token", "access_token": bootstrap_token},
        timeout=60,
    ).json()

    page_token = response.get("access_token")
    if not page_token:
        print("Meta no devolvio access_token para esa pagina.")
        print(response)
        return

    save_page_token(page_token)
    print("META_FB_PAGE_TOKEN actualizado en .env.")


if __name__ == "__main__":
    get_page_token()
