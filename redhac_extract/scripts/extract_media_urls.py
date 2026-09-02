"""
Extrae las URLs de fotos y videos de cada post de Instagram (sin descargarlos).
Guarda media_urls.json: {code: {imgs: [...], vids: [...]}}
Usado para llenar la columna Imagen del Excel y el .md.

Método igual que download_3_photos.py:
- /p/ → imgs >= 500px que NO estén en <a> (evita feed inferior)
- /reel/ → video_versions JSON embebido
"""
import json
import time
import requests
from pathlib import Path

CDP_HOST = "http://127.0.0.1:9222"
INPUT_JSON = Path(__file__).parent.parent / "output" / "ig_all_final.json"
OUT_JSON = Path(__file__).parent.parent / "output" / "media_urls.json"
MIN_WIDTH = 500

import websocket as ws_lib


class Cdp:
    def __init__(self, ws_url: str):
        self.ws = ws_lib.create_connection(ws_url, timeout=30)
        self.seq = 0

    def call(self, method: str, params: dict = None) -> dict:
        self.seq += 1
        mid = self.seq
        self.ws.send(json.dumps({"id": mid, "method": method, "params": params or {}}))
        while True:
            payload = json.loads(self.ws.recv())
            if payload.get("id") == mid:
                return payload.get("result", {})

    def eval(self, expression: str) -> object:
        result = self.call(
            "Runtime.evaluate",
            {"expression": expression, "awaitPromise": True, "returnByValue": True},
        )
        return result.get("result", {}).get("value")

    def close(self):
        try:
            self.ws.close()
        except Exception:
            pass


def extract_urls(cdp: Cdp, href: str) -> dict:
    is_reel = "/reel/" in href
    base_href = href.rstrip("/")
    cdp.call("Page.navigate", {"url": base_href})
    time.sleep(7)
    # Flush buffer
    cdp.ws.settimeout(0.5)
    while True:
        try:
            cdp.ws.recv()
        except Exception:
            break
    cdp.ws.settimeout(30)

    if is_reel:
        js = """
        (() => {
            const allScript = Array.from(document.querySelectorAll('script:not([src])')).map(s => s.textContent).join('');
            const matches = [...allScript.matchAll(/"video_versions":\\[(.*?)\\]/g)];
            if(matches.length > 0) {
                try {
                    const arr = JSON.parse('[' + matches[0][1] + ']');
                    arr.sort((a,b) => b.width - a.width);
                    return arr[0].url;
                } catch(e) {}
            }
            return null;
        })()
        """
        raw = cdp.eval(js)
        return {"imgs": [], "vids": [raw] if raw else []}

    # /p/ → fotos del post (no del feed inferior, que están en <a>)
    js = f"""
    (() => {{
        const imgs = Array.from(document.querySelectorAll('img'))
            .filter(i => i.naturalWidth >= {MIN_WIDTH} && !i.closest('a'))
            .map(i => i.src);
        return JSON.stringify({{imgs}});
    }})()
    """
    raw = cdp.eval(js)
    imgs = json.loads(raw)["imgs"] if raw else []

    # Deduplicar por path base
    seen = {}
    for u in imgs:
        key = u.split("?")[0][:80]
        if key not in seen:
            seen[key] = u
    imgs = list(seen.values())

    return {"imgs": imgs, "vids": []}


def main():
    if not INPUT_JSON.exists():
        print(f"Error: No se encontró {INPUT_JSON}")
        return

    data = json.loads(INPUT_JSON.read_text(encoding="utf-8"))
    media = data.get("media", [])
    if not media:
        print("No hay posts en el JSON.")
        return

    # Cargar progreso anterior si existe
    result = {}
    if OUT_JSON.exists():
        result = json.loads(OUT_JSON.read_text(encoding="utf-8"))
        print(f"Continuando desde progreso anterior: {len(result)} posts ya procesados.")

    r = requests.put(f"{CDP_HOST}/json/new?about:blank", timeout=10)
    tab_id = r.json()["id"]
    cdp = Cdp(r.json()["webSocketDebuggerUrl"])
    cdp.call("Page.enable")
    cdp.call("Runtime.enable")

    print(f"Extrayendo URLs de {len(media)} posts...\n")

    for idx, m in enumerate(media, start=1):
        href = m["href"]
        code = href.rstrip("/").split("/")[-1]

        # Saltar si ya fue procesado
        if code in result:
            print(f"[{idx}/{len(media)}] {code} → ya procesado, saltando.")
            continue

        print(f"[{idx}/{len(media)}] {code}  {href}")
        try:
            urls = extract_urls(cdp, href)
            result[code] = {
                "href": href,
                "imgs": urls["imgs"],
                "vids": urls["vids"],
            }
            print(f"  → {len(urls['imgs'])} foto(s) | {len(urls['vids'])} video(s)")
        except Exception as e:
            print(f"  ✗ Error: {e}")
            result[code] = {"href": href, "imgs": [], "vids": [], "error": str(e)}

        # Guardar progreso después de cada post
        OUT_JSON.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")

    cdp.close()
    requests.get(f"{CDP_HOST}/json/close/{tab_id}", timeout=5)
    print(f"\n✓ URLs guardadas en: {OUT_JSON}")
    print(f"  Total posts procesados: {len(result)}")


if __name__ == "__main__":
    main()
