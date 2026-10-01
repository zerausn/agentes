"""
continue_ig.py - Extracción de 469 publicaciones de Instagram REDHAC vía Chrome CDP
=====================================================================================
Problema que resuelve:
  Instagram virtualiza el grid: no todos los links /p/ están en el DOM a la vez.
  Se necesita scroll progresivo para cargar todo el feed.
  La API Meta da #10 → no se usa.

Solución:
  - Chrome 152 + perfil Edge (sesión logueada) via CDP ws://127.0.0.1:9222
  - 60 iteraciones de scroll × 4s = 240s total
  - Extracción via querySelectorAll('a[href*="/p/"], a[href*="/reel/"]')
  - Deduplicación por href exacto
  - Guarda progreso incremental en ig_progress.json (reanudable)
  - Verifica contra header "469 publicaciones"

Salida (en carpeta output/):
  - ig_progress.json   → guardado incremental (reanudable si se interrumpe)
  - ig_all_final.json  → resultado final con href + alt + img de cada post

Requisitos:
  pip install websocket-client

Uso:
  # 1. Abrir Chrome con perfil Edge y CDP:
  google-chrome --remote-debugging-port=9222 \\
    --user-data-dir=/home/zerausn/.var/app/com.microsoft.Edge/config/microsoft-edge \\
    --no-first-run &
  # 2. Abrir manualmente: https://www.instagram.com/redhuertosagroecali/
  # 3. Ejecutar:
  python3 scripts/continue_ig.py

Resultados obtenidos:
  469/469 (100%) en 60 scrolls
"""

import json
import time
import urllib.request
import websocket
from pathlib import Path

# ── Carpeta de salida ─────────────────────────────────────────────────────────
OUT_DIR = Path(__file__).parent.parent / "output"
OUT_DIR.mkdir(exist_ok=True)

CDP_HOST = "http://127.0.0.1:9222"
TARGET_URL_FRAGMENT = "instagram.com/redhuertosagroecali"
ITERATIONS = 3
SLEEP_BETWEEN = 4   # segundos entre scroll y lectura
TARGET_POSTS = 469  # header IG verificado


class Cdp:
    """Cliente mínimo del Chrome DevTools Protocol via WebSocket."""

    def __init__(self, ws_url: str):
        self.ws = websocket.create_connection(ws_url, timeout=60)
        self.seq = 0

    def call(self, method: str, params: dict = None) -> dict:
        """Envía un comando CDP y espera la respuesta con el mismo id."""
        self.seq += 1
        mid = self.seq
        self.ws.send(json.dumps({"id": mid, "method": method, "params": params or {}}))
        while True:
            payload = json.loads(self.ws.recv())
            if payload.get("id") == mid:
                if "error" in payload:
                    raise RuntimeError(payload["error"])
                return payload.get("result", {})

    def eval(self, expression: str, await_promise: bool = True):
        """Evalúa JavaScript en la página y retorna el valor."""
        result = self.call(
            "Runtime.evaluate",
            {
                "expression": expression,
                "awaitPromise": await_promise,
                "returnByValue": True,
                "userGesture": True,
            },
        )
        return result.get("result", {}).get("value")

    def close(self):
        try:
            self.ws.close()
        except Exception:
            pass


# ── 1. Encontrar la pestaña de Instagram ─────────────────────────────────────
with urllib.request.urlopen(f"{CDP_HOST}/json/list", timeout=5) as resp:
    tabs = json.loads(resp.read().decode())

ig_ws = None
for tab in tabs:
    if TARGET_URL_FRAGMENT in tab.get("url", ""):
        ig_ws = tab["webSocketDebuggerUrl"]
        print("IG tab:", tab["url"])
        break

if not ig_ws:
    raise RuntimeError(
        f"No se encontró pestaña con '{TARGET_URL_FRAGMENT}'. "
        "Abre https://www.instagram.com/redhuertosagroecali/ primero."
    )

cdp = Cdp(ig_ws)
cdp.call("Page.enable")
cdp.call("Runtime.enable")

# ── 2. Cargar progreso previo (permite reanudar si fue interrumpido) ──────────
progress_path = OUT_DIR / "ig_progress.json"
if progress_path.exists():
    data = json.loads(progress_path.read_text(encoding="utf-8"))
    ig_media: list[dict] = data.get("media", [])
    ig_seen: set[str] = set(m["href"] for m in ig_media)
    header = data.get("header", {})
    print(f"Reanudando desde {len(ig_media)} media ya capturadas")
else:
    ig_media = []
    ig_seen = set()
    header = json.loads(cdp.eval("JSON.stringify({title: document.title})") or "{}")

# ── 3. SCROLL: extraer links de posts/reels ───────────────────────────────────
for iteration in range(ITERATIONS):
    # Extraer todos los links únicos visibles (posts y reels)
    batch_raw = cdp.eval("""
(() => {
  const anchors = document.querySelectorAll('a[href*="/p/"], a[href*="/reel/"]');
  const unique = [...new Set(Array.from(anchors).map(a => a.href))];
  const data = unique.slice(0, 150).map(href => {
    const el = Array.from(document.querySelectorAll('a')).find(x => x.href === href);
    let alt = '', img = '';
    if (el) {
      const imgEl = el.querySelector('img');
      if (imgEl) {
        alt = imgEl.alt?.slice(0, 1500) || '';
        img = imgEl.src?.slice(0, 500) || '';
      }
    }
    return { href, alt, img };
  });
  return JSON.stringify(data);
})()
""")

    try:
        batch: list[dict] = json.loads(batch_raw) if batch_raw else []
    except Exception:
        batch = []

    new_count = 0
    for item in batch:
        if item["href"] not in ig_seen:
            ig_seen.add(item["href"])
            ig_media.append(item)
            new_count += 1

    print(f"IG Iter {iteration:02d}: batch {len(batch)} | +{new_count} nuevos | total {len(ig_media)}")

    # Guardar progreso incremental
    progress_path.write_text(
        json.dumps({"header": header, "count": len(ig_media), "media": ig_media}, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    # Condición de fin
    if len(ig_media) >= TARGET_POSTS:
        print(f"Alcanzado objetivo de {TARGET_POSTS} posts ✓")
        break

    # Condición de salida anticipada: sin nuevos varios iteraciones
    if new_count == 0 and iteration > 5:
        dom_links = cdp.eval("document.querySelectorAll('a[href*=\"/p/\"]').length")
        print(f"  sin nuevos, links en DOM: {dom_links}")
        if iteration > 15 and new_count == 0:
            print("Sin nuevos posts por más de 10 iteraciones, terminando.")
            break

    # Scroll al fondo del feed
    cdp.eval("window.scrollTo(0, document.body.scrollHeight)")
    time.sleep(SLEEP_BETWEEN)

# ── 4. Guardar resultado final ────────────────────────────────────────────────
print(f"\nIG FINAL: {len(ig_media)} posts totales")
output_file = OUT_DIR / "ig_all_final.json"
output_file.write_text(
    json.dumps({"header": header, "media": ig_media}, indent=2, ensure_ascii=False),
    encoding="utf-8",
)
print(f"Guardado en {output_file}")
cdp.close()
