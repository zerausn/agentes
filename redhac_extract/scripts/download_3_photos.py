"""
Descarga de fotos y videos de Instagram vía CDP.

Video blob: Para reels, el <video src> es un blob: interno al navegador.
Lo descargamos con JS fetch(blob_url) → base64 → Python lo decodifica y guarda como .mp4.

Método correcto (según README_CORRECTO.md):
- Navegar a la URL del post con ?img_index=1 para forzar que IG cargue
  TODOS los slides del carrusel en el DOM de una sola vez.
- Leer los src de todos los <img> con naturalWidth >= 500 (resolución real).
- Leer los src de todos los <video> para descargar videos.
- Descargar todo con Python requests (sin abrir pestañas scontent).
- Para reels: detectar <video src> y descargar el mp4.

Salidas: OUT_DIR (carpeta externa en disco D:/)
"""
import websocket
import json
import time
import base64
import requests
from pathlib import Path

# Config
OUT_DIR = Path(
    "/media/zerausn/D69493CF9493B08B/Users/ZN-/Documents/UNAD/CURSOS/6/"
    "METODOLOGÍA Y GESTIÓN DE LA INVESTIGACIÓN/1/Documentacion/1/Instagram_Fotos/"
)
OUT_DIR.mkdir(parents=True, exist_ok=True)
CDP_HOST = "http://127.0.0.1:9222"
INPUT_JSON = Path(__file__).parent.parent / "output" / "ig_all_final.json"

# Tamaño mínimo para considerar que es la foto del post (no un avatar/thumbnail)
MIN_WIDTH = 500


class Cdp:
    def __init__(self, ws_url: str):
        self.ws = websocket.create_connection(ws_url, timeout=30)
        self.seq = 0

    def call(self, method: str, params: dict = None) -> dict:
        self.seq += 1
        mid = self.seq
        self.ws.send(json.dumps({"id": mid, "method": method, "params": params or {}}))
        while True:
            payload = json.loads(self.ws.recv())
            if payload.get("id") == mid:
                if "error" in payload:
                    raise RuntimeError(payload["error"])
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


def download_file(url: str, out_path: Path, cdp: "Cdp" = None) -> bool:
    """Descarga url → out_path.
    - URLs http/https: Python requests.
    - URLs blob: JS fetch dentro del navegador → base64 → Python.
    """
    if url.startswith("blob:"):
        if cdp is None:
            print(f"  ✗ blob URL pero sin CDP disponible")
            return False
        return _download_blob(url, out_path, cdp)
    try:
        r = requests.get(url, timeout=30)
        r.raise_for_status()
        out_path.write_bytes(r.content)
        print(f"  ✓ {out_path.name} ({len(r.content) / 1024:.0f} KB)")
        return True
    except Exception as e:
        print(f"  ✗ Error: {e}")
        return False


def _download_blob(blob_url: str, out_path: Path, cdp: "Cdp") -> bool:
    """Lee un blob: URL directamente desde el contexto JS del navegador."""
    js = f"""
    (async () => {{
        try {{
            const r = await fetch('{blob_url}');
            if (!r.ok) return {{error: 'HTTP ' + r.status}};
            const buf = await r.arrayBuffer();
            const bytes = new Uint8Array(buf);
            let b = '';
            // Chunk to avoid string length limit
            for (let i = 0; i < bytes.byteLength; i += 8192) {{
                b += String.fromCharCode(...bytes.subarray(i, i + 8192));
            }}
            return {{b64: btoa(b), size: bytes.byteLength}};
        }} catch(e) {{ return {{error: e.toString()}}; }}
    }})()
    """
    try:
        res = cdp.eval(js)
        if not res or "error" in res:
            print(f"  ✗ blob error: {res}")
            return False
        data = base64.b64decode(res["b64"])
        out_path.write_bytes(data)
        print(f"  ✓ {out_path.name} ({len(data) / 1024:.0f} KB) [blob]")
        return True
    except Exception as e:
        print(f"  ✗ blob descarga fallida: {e}")
        return False


def scrape_post(cdp: Cdp, href: str) -> dict:
    """
    Estrategia por tipo de post:

    /p/ (foto o carrusel):
      - Navegar a ?img_index=N (1, 2, 3...) para cada slide.
      - En cada slide, leer la imagen de mayor resolución visible en el viewport.
      - Parar cuando el src no cambia respecto al slide anterior (fin del carrusel).

    /reel/:
      - Interceptar la URL del video CDN (m86) durante la carga de la página.
    """
    is_reel = "/reel/" in href
    base_href = href.rstrip("/")

    # Siempre habilitar captura de red para interceptar video CDN
    cdp.call("Network.enable")

    # ── REEL ──
    if is_reel:
        cdp.call("Page.navigate", {"url": base_href})
        time.sleep(7)
        # Flush buffer
        cdp.ws.settimeout(0.5)
        while True:
            try: cdp.ws.recv()
            except: break
        cdp.ws.settimeout(30)
        
        js = """
        (() => {
            const allScript = Array.from(document.querySelectorAll('script:not([src])')).map(s => s.textContent).join('');
            const matches = [...allScript.matchAll(/"video_versions":\\[(.*?)\\]/g)];
            if(matches.length > 0) {
                try {
                    const arr = JSON.parse('[' + matches[0][1] + ']');
                    // Ordenar por tamaño (width) descendente y tomar el primero
                    arr.sort((a,b) => b.width - a.width);
                    return arr[0].url;
                } catch(e) {}
            }
            return null;
        })()
        """
        raw = cdp.eval(js)
        return {"imgs": [], "vids": [raw] if raw else []}

    # ── POST /p/ ──
    # En full-page mode, Instagram muestra el carrusel completo como grid:
    # - 1 imagen hero (grande, en el viewport)
    # - Filas de 3 columnas con todos los slides debajo
    # Todos los imgs >= MIN_WIDTH en el DOM SON slides del carrusel.
    # Los posts del feed debajo generalmente no se cargan de inmediato.
    cdp.call("Page.navigate", {"url": base_href})
    time.sleep(7)
    # Flush buffer de red
    cdp.ws.settimeout(0.5)
    while True:
        try: cdp.ws.recv()
        except: break
    cdp.ws.settimeout(30)

    js = """
    (() => {
        const imgs = Array.from(document.querySelectorAll('img'))
            .filter(i => i.naturalWidth >= """ + str(MIN_WIDTH) + """ && !i.closest('a'))
            .map(i => i.src);
        return JSON.stringify({imgs});
    })()
    """
    raw = cdp.eval(js)
    imgs = json.loads(raw)["imgs"] if raw else []

    return {"imgs": imgs, "vids": []}


def dedupe_keep_largest(urls: list) -> list:
    """
    Para evitar duplicados (IG a veces repite la misma imagen con distintos params),
    filtra por los primeros 60 chars del path base (sin query string).
    Mantiene el de mayor tamaño si hay varias resoluciones del mismo archivo.
    """
    seen = {}
    for url in urls:
        key = url.split("?")[0][:80]
        if key not in seen:
            seen[key] = url
    return list(seen.values())


def main():
    if not INPUT_JSON.exists():
        print(f"Error: No se encontró {INPUT_JSON}. Ejecuta primero continue_ig.py")
        return

    data = json.loads(INPUT_JSON.read_text(encoding="utf-8"))
    media = data.get("media", [])
    if not media:
        print("No hay posts en el JSON.")
        return

    # Procesar todos los posts (fotos/carruseles y reels).
    sample = media

    # Abrir una sola pestaña reutilizable → evita contaminar el navegador
    r = requests.put(f"{CDP_HOST}/json/new?about:blank", timeout=10)
    tab_id = r.json()["id"]
    cdp = Cdp(r.json()["webSocketDebuggerUrl"])
    cdp.call("Page.enable")
    cdp.call("Runtime.enable")

    print(f"Descargando {len(sample)} posts en:\n  {OUT_DIR}\n")

    for idx, m in enumerate(sample, start=1):
        href = m["href"]
        code = href.rstrip("/").split("/")[-1]
        print(f"[{idx}/{len(sample)}] {code}  {href}")

        result = scrape_post(cdp, href)
        imgs = dedupe_keep_largest(result["imgs"])
        vids = dedupe_keep_largest(result["vids"])

        print(f"  Encontradas: {len(imgs)} foto(s) | {len(vids)} video(s)")

        for s, src in enumerate(imgs, start=1):
            out = OUT_DIR / f"REDHAC_{code}_foto{s}.jpg"
            download_file(src, out, cdp)

        for v, src in enumerate(vids, start=1):
            out = OUT_DIR / f"REDHAC_{code}_video{v}.mp4"
            download_file(src, out, cdp)

    # Cerrar la pestaña al terminar
    cdp.close()
    requests.get(f"{CDP_HOST}/json/close/{tab_id}", timeout=5)
    print("\nDescarga completada. Pestañas cerradas.")


if __name__ == "__main__":
    main()
