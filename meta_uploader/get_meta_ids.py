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


def main():
    load_local_env()
    api_version = os.environ.get("META_GRAPH_API_VERSION", "v19.0").strip() or "v19.0"
    token = os.environ.get("META_PAGE_TOKEN", "")
    if not token:
        print("No se encontro META_PAGE_TOKEN en .env.")
        return

    print("Consultando Meta para obtener Page ID e IG User ID...")
    accounts_url = f"https://graph.facebook.com/{api_version}/me/accounts"
    accounts = requests.get(accounts_url, params={"access_token": token}, timeout=60).json()

    pages = accounts.get("data") or []
    if not pages:
        print("No se encontraron paginas accesibles con ese token.")
        print(accounts)
        return

    for page in pages:
        page_name = page.get("name", "(sin nombre)")
        page_id = page.get("id")
        print(f"\nPagina: {page_name}")
        print(f"META_FB_PAGE_ID={page_id}")

        page_url = f"https://graph.facebook.com/{api_version}/{page_id}"
        page_details = requests.get(
            page_url,
            params={"fields": "instagram_business_account", "access_token": token},
            timeout=60,
        ).json()

        ig_account = page_details.get("instagram_business_account") or {}
        if ig_account.get("id"):
            print(f"META_IG_USER_ID={ig_account['id']}")
        else:
            print("La pagina no reporto una cuenta de Instagram enlazada.")


if __name__ == "__main__":
    main()
