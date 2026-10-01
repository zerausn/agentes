"""
download_media_fb.py — Descarga de medios de Facebook.
"""

import json
import time
import argparse
import requests
import websocket
from pathlib import Path

OUT_JSON = Path(__file__).parent.parent / "output" / "fb_full_data.json"
DEST_DIR = Path(
    "/media/zerausn/D69493CF9493B08B/Users/ZN-/Documents/UNAD/CURSOS/6/"
    "METODOLOGÍA Y GESTIÓN DE LA INVESTIGACIÓN/1/Documentacion/1/media"
)
CDP_HOST = "http://127.0.0.1:9222"
POLL_INTERVAL = 30

def get_session_cookies() -> dict:
    try:
        tabs = requests.get(f"{CDP_HOST}/json", timeout=5).json()
        fb_tabs = [t for t in tabs if "facebook.com" in t.get("url", "")]
        if not fb_tabs:
            fb_tabs = tabs[:1]
        if not fb_tabs:
            return {}

        ws_url = fb_tabs[0]["webSocketDebuggerUrl"]
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
        print(f"  ⚠ No se pudieron obtener cookies: {e}")
        return {}

def download_file(url: str, dest: Path, cookies: dict) -> bool:
    if dest.exists() and dest.stat().st_size > 1024:
        return True

    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
            "Referer": "https://www.facebook.com/",
            "Accept": "*/*",
        }
        resp = requests.get(url, headers=headers, cookies=cookies, timeout=30, stream=True)
        if resp.status_code != 200:
            print(f"    ✗ HTTP {resp.status_code} → {dest.name}")
            return False

        dest.parent.mkdir(parents=True, exist_ok=True)
        with open(dest, "wb") as f:
            for chunk in resp.iter_content(chunk_size=65536):
                if chunk: f.write(chunk)

        size_kb = dest.stat().st_size // 1024
        if size_kb < 2:
            dest.unlink()
            return False

        print(f"    ✓ {dest.name} ({size_kb}KB)")
        return True
    except Exception as e:
        print(f"    ✗ Error descargando {dest.name}: {e}")
        return False

def process_post(code: str, data: dict, cookies: dict) -> tuple[int, int]:
    downloaded = 0
    skipped = 0

    imgs = data.get("imgs", [])
    vids = data.get("vids", [])

    for i, url in enumerate(imgs, start=1):
        dest = DEST_DIR / f"REDHAC_FB_{code}_foto{i}.jpg"
        if dest.exists() and dest.stat().st_size > 1024:
            skipped += 1
            continue
        if download_file(url, dest, cookies):
            downloaded += 1

    for i, url in enumerate(vids, start=1):
        dest = DEST_DIR / f"REDHAC_FB_{code}_video{i}.mp4"
        if dest.exists() and dest.stat().st_size > 1024:
            skipped += 1
            continue
        if download_file(url, dest, cookies):
            downloaded += 1

    return downloaded, skipped

def run(once: bool = False):
    DEST_DIR.mkdir(parents=True, exist_ok=True)
    print(f"Carpeta destino: {DEST_DIR}")
    print(f"Fuente JSON: {OUT_JSON}\\n")

    processed_codes: set = set()
    total_downloaded = 0
    total_skipped = 0

    cookies = get_session_cookies()
    cookie_refresh_counter = 0

    while True:
        if not OUT_JSON.exists():
            if once: break
            time.sleep(POLL_INTERVAL)
            continue

        try:
            data_all: dict = json.loads(OUT_JSON.read_text(encoding="utf-8"))
        except Exception:
            time.sleep(5)
            continue

        new_codes = [c for c in data_all if c not in processed_codes]

        if new_codes:
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

        if once: break
        time.sleep(POLL_INTERVAL)

    print(f"\\n✓ Descarga terminada. Total: {total_downloaded} descargados, {total_skipped} existían.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--once", action="store_true")
    args = parser.parse_args()
    run(once=args.once)
