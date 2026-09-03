"""
download_media.py — Descarga física de fotos y videos de los 469 posts de REDHAC.
==================================================================================

Funciona en paralelo con scrape_ig_full.py:
  - Monitorea output/ig_full_data.json cada 30s
  - Por cada post nuevo que aparezca, descarga todas sus fotos y videos
  - Nombres: REDHAC_{code}_foto1.jpg, REDHAC_{code}_foto2.jpg, REDHAC_{code}_video1.mp4
  - Reanudable: si el archivo ya existe, lo omite (no lo re-descarga)
  - Usa la sesión activa del navegador (CDP) para pasar el token en las cookies
    (las URLs de CDN de Instagram/Facebook requieren autenticación implícita)

Carpeta destino:
  /media/zerausn/D69493CF9493B08B/Users/ZN-/.../Documentacion/1/media/

Uso:
  # En una segunda terminal, mientras scrape_ig_full.py ya está corriendo:
  cd /home/zerausn/Documents/Antigravity/agentes/redhac_extract
  python3 scripts/download_media.py

  # O también después de que el scraper termina (descarga los que faltan):
  python3 scripts/download_media.py --once   # una sola pasada, sin loop

Requisitos:
  pip install websocket-client requests
  Chrome con sesión IG activa en CDP ws://127.0.0.1:9222
"""

import json
import time
import sys
import argparse
import hashlib
import requests
import websocket
from pathlib import Path

# ── Rutas ─────────────────────────────────────────────────────────────────────
OUT_JSON = Path(__file__).parent.parent / "output" / "ig_full_data.json"
DEST_DIR = Path(
    "/media/zerausn/D69493CF9493B08B/Users/ZN-/Documents/UNAD/CURSOS/6/"
    "METODOLOGÍA Y GESTIÓN DE LA INVESTIGACIÓN/1/Documentacion/1/media"
)
CDP_HOST = "http://127.0.0.1:9222"
POLL_INTERVAL = 30  # segundos entre checks cuando corre en modo --watch


# ── Obtener cookies de la sesión activa del navegador ────────────────────────
def get_session_cookies() -> dict:
    """
    Extrae cookies de la sesión de Instagram del navegador vía CDP.
    Las URLs de scontent.cdninstagram.com requieren el contexto de sesión.
    """
    try:
        tabs = requests.get(f"{CDP_HOST}/json", timeout=5).json()
        ig_tabs = [t for t in tabs if "instagram.com" in t.get("url", "")]
        if not ig_tabs:
            # Usar la primera pestaña disponible
            ig_tabs = tabs[:1]
        if not ig_tabs:
            return {}

        ws_url = ig_tabs[0]["webSocketDebuggerUrl"]
        ws = websocket.create_connection(ws_url, timeout=10)

        ws.send(json.dumps({"id": 1, "method": "Network.getCookies", "params": {}}))
        while True:
            d = json.loads(ws.recv())
            if d.get("id") == 1:
                cookies_raw = d.get("result", {}).get("cookies", [])
                break

        ws.close()
        return {c["name"]: c["value"] for c in cookies_raw}
    except Exception as e:
        print(f"  ⚠ No se pudieron obtener cookies del navegador: {e}")
        return {}


# ── Descarga de un archivo individual ─────────────────────────────────────────
def download_file(url: str, dest: Path, cookies: dict) -> bool:
    """
    Descarga url a dest usando las cookies de sesión.
    Retorna True si exitoso, False si falló.
    """
    if dest.exists() and dest.stat().st_size > 1024:
        return True  # ya existe y no está corrupto

    try:
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"
            ),
            "Referer": "https://www.instagram.com/",
            "Accept": "*/*",
        }
        resp = requests.get(url, headers=headers, cookies=cookies, timeout=30, stream=True)
        if resp.status_code != 200:
            print(f"    ✗ HTTP {resp.status_code} → {dest.name}")
            return False

        dest.parent.mkdir(parents=True, exist_ok=True)
        with open(dest, "wb") as f:
            for chunk in resp.iter_content(chunk_size=65536):
                if chunk:
                    f.write(chunk)

        size_kb = dest.stat().st_size // 1024
        if size_kb < 2:
            dest.unlink()
            print(f"    ✗ Archivo muy pequeño ({size_kb}KB, probablemente 403) → {dest.name}")
            return False

        print(f"    ✓ {dest.name} ({size_kb}KB)")
        return True
    except Exception as e:
        print(f"    ✗ Error descargando {dest.name}: {e}")
        return False


# ── Proceso de un post ────────────────────────────────────────────────────────
def process_post(code: str, data: dict, cookies: dict) -> tuple[int, int]:
    """
    Descarga todas las fotos y videos de un post.
    Retorna (downloaded, skipped).
    """
    downloaded = 0
    skipped = 0

    imgs = data.get("imgs", [])
    vids = data.get("vids", [])

    for i, url in enumerate(imgs, start=1):
        dest = DEST_DIR / f"REDHAC_{code}_foto{i}.jpg"
        if dest.exists() and dest.stat().st_size > 1024:
            skipped += 1
            continue
        ok = download_file(url, dest, cookies)
        if ok:
            downloaded += 1

    for i, url in enumerate(vids, start=1):
        dest = DEST_DIR / f"REDHAC_{code}_video{i}.mp4"
        if dest.exists() and dest.stat().st_size > 1024:
            skipped += 1
            continue
        ok = download_file(url, dest, cookies)
        if ok:
            downloaded += 1

    return downloaded, skipped


# ── Bucle principal ────────────────────────────────────────────────────────────
def run(once: bool = False):
    DEST_DIR.mkdir(parents=True, exist_ok=True)
    print(f"Carpeta destino: {DEST_DIR}")
    print(f"Fuente JSON: {OUT_JSON}")
    print()

    processed_codes: set = set()
    total_downloaded = 0
    total_skipped = 0

    # Refrescar cookies cada N iteraciones
    cookies = get_session_cookies()
    cookie_refresh_counter = 0

    while True:
        if not OUT_JSON.exists():
            if once:
                print("No existe ig_full_data.json todavía. Esperando scraper...")
                break
            print(f"  Esperando que exista {OUT_JSON.name}...")
            time.sleep(POLL_INTERVAL)
            continue

        try:
            data_all: dict = json.loads(OUT_JSON.read_text(encoding="utf-8"))
        except Exception as e:
            print(f"  Error leyendo JSON: {e}")
            time.sleep(5)
            continue

        new_codes = [c for c in data_all if c not in processed_codes]

        if new_codes:
            # Refrescar cookies si han pasado muchos posts
            cookie_refresh_counter += len(new_codes)
            if cookie_refresh_counter > 50:
                cookies = get_session_cookies()
                cookie_refresh_counter = 0

            for code in new_codes:
                pdata = data_all[code]
                if "error" in pdata and len(pdata) == 2:
                    processed_codes.add(code)
                    continue

                n_imgs = len(pdata.get("imgs", []))
                n_vids = len(pdata.get("vids", []))

                if n_imgs + n_vids == 0:
                    processed_codes.add(code)
                    continue

                print(f"  [{len(processed_codes)+1}/{len(data_all)}] {code} — {n_imgs} fotos, {n_vids} videos")
                dl, sk = process_post(code, pdata, cookies)
                total_downloaded += dl
                total_skipped += sk
                processed_codes.add(code)
        else:
            total = len(data_all)
            pct = len(processed_codes) / max(total, 1) * 100
            print(f"  Sin cambios. {len(processed_codes)}/{total} posts procesados ({pct:.1f}%). Esperando {POLL_INTERVAL}s...")

        if once:
            break

        time.sleep(POLL_INTERVAL)

    print(f"\n✓ Descarga terminada. Total: {total_downloaded} archivos descargados, {total_skipped} ya existían.")


# ── Entry point ────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--once", action="store_true", help="Una sola pasada (no loop)")
    args = parser.parse_args()
    run(once=args.once)
