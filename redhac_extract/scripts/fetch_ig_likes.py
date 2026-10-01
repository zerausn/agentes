"""
fetch_ig_likes.py - Extracción de likes por post de Instagram REDHAC vía CDP
=============================================================================
Problema que resuelve:
  Instagram CDN (scontent.cdninstagram.com) devuelve 403 si abres la URL de
  imagen directamente (curl, nueva pestaña sin contexto). El hash de la URL
  requiere la sesión activa del navegador.

Solución (método correcto):
  1. Crear pestaña nueva via CDP /json/new
  2. Navegar a cada href del post (instagram.com/.../p/CODE/)
  3. Esperar 6s a que cargue el article con la imagen
  4. Extraer likes desde og:description ("X likes, Y comments")
  5. Extraer og:image para URL de foto 1440px limpia
  6. Si se quiere descargar la foto: fetch() con credentials:include
     dentro de la pestaña IG (mismo origen = sin CORS)

NUNCA abrir scontent.cdninstagram.com directamente → 403 Bad URL hash

Salida (en carpeta output/):
  - ig_likes_sample.json  → primeros 15 posts con likes/comments/date/ogDesc

Requisitos:
  pip install websocket-client requests

Uso:
  # 1. Requiere output/ig_all_final.json generado por continue_ig.py
  # 2. Chrome abierto con sesión IG:
  google-chrome --remote-debugging-port=9222 \\
    --user-data-dir=/home/zerausn/.var/app/com.microsoft.Edge/config/microsoft-edge \\
    --no-first-run &
  # 3. Ejecutar:
  python3 scripts/fetch_ig_likes.py

Nota de escala:
  469 posts × 6s ≈ 47 min para likes completos.
  Este script hace solo los primeros 15 como muestra.
  Para hacer todos: cambiar sample = ig_data["media"] (sin slice)
"""

import websocket
import json
import urllib.request
import time
import re
import requests
from pathlib import Path

# ── Carpeta de salida ─────────────────────────────────────────────────────────
OUT_DIR = Path(__file__).parent.parent / "output"
OUT_DIR.mkdir(exist_ok=True)

CDP_HOST = "http://127.0.0.1:9222"
SLEEP_PER_POST = 6   # segundos de espera por post (carga de article + og:description)
SLEEP_BETWEEN = 2    # segundos adicionales entre posts


class Cdp:
    """Cliente mínimo del Chrome DevTools Protocol via WebSocket."""

    def __init__(self, ws_url: str):
        self.ws = websocket.create_connection(ws_url, timeout=30)
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


# ── 1. Crear pestaña nueva para navegación post a post ───────────────────────
r = requests.put(f"{CDP_HOST}/json/new?about:blank", timeout=10)
post_ws = r.json()["webSocketDebuggerUrl"]
print("Pestaña de posts:", post_ws)

cdp = Cdp(post_ws)
cdp.call("Page.enable")
cdp.call("Runtime.enable")

# ── 2. Cargar lista de media generada por continue_ig.py ─────────────────────
ig_final_path = OUT_DIR / "ig_all_final.json"
if not ig_final_path.exists():
    raise FileNotFoundError(
        f"No se encontró {ig_final_path}. "
        "Ejecuta primero scripts/continue_ig.py para generar ig_all_final.json"
    )

ig_data = json.loads(ig_final_path.read_text(encoding="utf-8"))
# Muestra: primeros 15. Para todos: ig_data["media"] (sin slice)
sample = ig_data["media"][:3]

# ── 3. Extraer likes/comments/date por post ───────────────────────────────────
results: list[dict] = []

for idx, media in enumerate(sample, start=1):
    href = media["href"]
    print(f"\n{idx}/{len(sample)}. Fetching: {href[:70]}")

    # Navegar al post
    cdp.call("Page.navigate", {"url": href})
    time.sleep(SLEEP_PER_POST)

    # Extraer metadata desde innerText + og:description
    info_raw = cdp.eval("""
(() => {
  const txt = document.body.innerText;

  // Likes: "X Me gusta" (ES) o "X likes" (EN)
  let likes = '';
  let m = txt.match(/([0-9.,]+)\s*Me gusta/);
  if (m) {
    likes = m[0];
  } else {
    m = txt.match(/([0-9.,]+)\s*likes?/i);
    if (m) likes = m[0];
  }

  // Comentarios
  let comments = '';
  const mc = txt.match(/([0-9]+)\s*comentarios?/i);
  if (mc) comments = mc[0];

  // Fecha desde elemento <time>
  let date = '';
  const timeEl = document.querySelector('time');
  if (timeEl) date = timeEl.getAttribute('datetime') || timeEl.innerText;

  // og:description tiene formato "X likes, Y comments - username: caption"
  const ogDesc = document.querySelector('meta[property="og:description"]')?.content || '';
  if (!likes) {
    const m2 = ogDesc.match(/([0-9.,]+)\s*likes?/i);
    if (m2) likes = m2[0];
  }

  // og:image → URL fresca de la foto 1440px (válida solo con sesión activa)
  const ogImage = document.querySelector('meta[property="og:image"]')?.content || '';

  return JSON.stringify({
    likes,
    comments,
    date,
    ogDesc: ogDesc.slice(0, 300),
    ogImage: ogImage.slice(0, 500),
    txtSnippet: txt.slice(0, 800),
  });
})()
""")

    print(f"  Info: {info_raw[:400] if info_raw else '(vacío)'}")

    try:
        obj = json.loads(info_raw) if info_raw else {}
    except Exception:
        obj = {}

    obj["href"] = href
    obj["alt"] = media.get("alt", "")[:300]
    results.append(obj)

    time.sleep(SLEEP_BETWEEN)

# ── 4. Guardar resultados ─────────────────────────────────────────────────────
output_file = OUT_DIR / "ig_likes_sample.json"
output_file.write_text(
    json.dumps(results, indent=2, ensure_ascii=False),
    encoding="utf-8",
)
print(f"\nDone: {len(results)} posts procesados → {output_file}")

# Resumen
for item in results[:5]:
    print(
        f"  {item.get('href', '')[:50]} | likes: {item.get('likes', '-')} | "
        f"comments: {item.get('comments', '-')} | date: {item.get('date', '-')[:30]}"
    )

cdp.close()
