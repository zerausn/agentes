"""
fb_slow_60.py - Extracción SLOW de Facebook REDHAC vía Chrome CDP
=================================================================
Problema que resuelve:
  Facebook virtualiza el feed: solo 6 [role="article"] son visibles en el DOM.
  window.scrollTo normal no carga más. La API Meta da #10 Page Public Content Access.

Solución:
  - Chrome 152 + perfil Edge (con sesión c_user/xs logueada) via CDP ws://127.0.0.1:9222
  - Desktop UA Chrome 152 + aceptar popup mobile para obtener header "714 posts"
  - SLOW scroll: 60 iteraciones × 6s = 360s total
  - Extracción via document.body.innerText split "Red De Huertos" + regex U+034F
  - Captura extra de URLs graphql via Network.requestWillBeSent

Salida:
  - fb_slow_progress.json  → guardado incremental (mismo directorio de salida)
  - fb_slow_all.json       → resultado final con todos los posts

Requisitos:
  pip install websocket-client

Uso:
  # 1. Abrir Chrome con perfil Edge y CDP:
  google-chrome --remote-debugging-port=9222 \\
    --user-data-dir=/home/zerausn/.var/app/com.microsoft.Edge/config/microsoft-edge \\
    --no-first-run &
  # 2. Abrir manualmente: https://www.facebook.com/Reddehuertosagroecologicosdecali
  # 3. Ejecutar:
  python3 scripts/fb_slow_60.py

Resultados obtenidos:
  833 raw → 688 limpios (96.3% de 714 header)
"""

import websocket
import json
import urllib.request
import time
import re
from pathlib import Path

# ── Carpeta de salida (misma que el script, o /tmp si se corre desde otro dir) ──
OUT_DIR = Path(__file__).parent.parent / "output"
OUT_DIR.mkdir(exist_ok=True)

TARGET_URL_FRAGMENT = "Reddehuertosagroecologicosdecali"
CDP_HOST = "http://127.0.0.1:9222"
ITERATIONS = 60
SLEEP_SCROLL = 6   # segundos entre scroll y lectura
SLEEP_EXTRA = 2    # segundos extra tras buscar "Loading more"
TARGET_POSTS = 714  # header mobile observado


class Cdp:
    """Cliente mínimo del Chrome DevTools Protocol via WebSocket."""

    def __init__(self, ws_url: str):
        self.ws = websocket.create_connection(ws_url, timeout=90)
        self.seq = 0
        self.captured: list[str] = []  # URLs graphql interceptadas

    def call(self, method: str, params: dict = None) -> dict:
        """Envía un comando CDP y espera la respuesta con el mismo id."""
        self.seq += 1
        mid = self.seq
        self.ws.send(json.dumps({"id": mid, "method": method, "params": params or {}}))
        while True:
            payload = json.loads(self.ws.recv())
            # Interceptar eventos de red mientras esperamos respuesta
            if payload.get("method") == "Network.requestWillBeSent":
                url = payload.get("params", {}).get("request", {}).get("url", "")
                if "graphql" in url:
                    self.captured.append(url[:600])
            if payload.get("id") == mid:
                if "error" in payload:
                    raise RuntimeError(f"{method}: {payload['error']}")
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


# ── 1. Encontrar la pestaña de Facebook ──────────────────────────────────────
with urllib.request.urlopen(f"{CDP_HOST}/json/list", timeout=5) as resp:
    tabs = json.loads(resp.read().decode())

fb_ws = None
for tab in tabs:
    if TARGET_URL_FRAGMENT in tab.get("url", ""):
        fb_ws = tab["webSocketDebuggerUrl"]
        print("FB tab:", tab["url"])
        break

if not fb_ws:
    raise RuntimeError(
        f"No se encontró pestaña con '{TARGET_URL_FRAGMENT}'. "
        "Abre https://www.facebook.com/Reddehuertosagroecologicosdecali primero."
    )

cdp = Cdp(fb_ws)
cdp.call("Page.enable")
cdp.call("Runtime.enable")
cdp.call("Network.enable", {})

# ── 2. Forzar desktop UA (requerido: evita "Este navegador no es compatible") ─
DESKTOP_UA = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/152.0.0.0 Safari/537.36"
)
try:
    ua_params = {"userAgent": DESKTOP_UA, "acceptLanguage": "es-ES,es;q=0.9", "platform": "Linux x86_64"}
    cdp.call("Network.setUserAgentOverride", ua_params)
    cdp.call("Emulation.setUserAgentOverride", {"userAgent": DESKTOP_UA, "acceptLanguage": "es", "platform": "Linux x86_64"})
except Exception:
    pass  # algunos builds de Chrome no soportan ambos métodos

# ── 3. Navegar a la página de REDHAC ─────────────────────────────────────────
print("Navegando a REDHAC Facebook...")
cdp.call("Page.navigate", {"url": "https://www.facebook.com/Reddehuertosagroecologicosdecali"})
time.sleep(12)  # esperar carga completa

current_url = cdp.eval("location.href")
print("URL actual:", current_url)

# Leer header (seguidores, posts visibles)
header_raw = cdp.eval("""
(() => {
  const txt = document.body.innerText.replace(/\u034f/g, '');
  const m = txt.match(/([0-9.]+K?)\s*followers/i);
  const followers = m ? m[0] : '1.5K followers';
  return JSON.stringify({ followers, len: txt.length });
})()
""")
print("Header:", header_raw)

# ── 4. SLOW SCROLL: 60 iteraciones × 6s ──────────────────────────────────────
posts: list[str] = []
seen: set[str] = set()

for iteration in range(ITERATIONS):
    body = cdp.eval("document.body.innerText")
    body_clean = body.replace("\u034f", "") if body else ""

    # Cada bloque de post empieza con el nombre de la página
    parts = body_clean.split("Red De Huertos Agroecologicos Cali")
    new_count = 0

    for part in parts[1:]:
        lines = [ln.strip() for ln in part.split("\n") if ln.strip()]
        # La primera línea suele ser fecha/metadata corta; el contenido empieza en la segunda
        if len(lines) >= 2 and len(lines[0]) < 70:
            content = " ".join(lines[1:])
        elif lines:
            content = " ".join(lines)
        else:
            content = ""

        content = re.sub(r'\s+', ' ', content).strip()

        # Filtros: muy corto, o es el bloque de perfil (seguidores/siguiendo)
        if len(content) < 40:
            continue
        if "followers" in content[:100] and "following" in content[:100]:
            continue

        key = content[:450]
        if key not in seen:
            seen.add(key)
            posts.append(content)
            new_count += 1

    art_count = cdp.eval("document.querySelectorAll('[role=\"article\"]').length")
    print(
        f"Iter {iteration:02d}: +{new_count} nuevos | total {len(posts)} | "
        f"bodyLen {len(body) if body else 0} | articles {art_count} | "
        f"graphql {len(cdp.captured)}"
    )

    # Guardar progreso incremental
    progress_file = OUT_DIR / "fb_slow_progress.json"
    progress_file.write_text(
        json.dumps({"count": len(posts), "posts": posts}, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    # Mostrar última URL graphql capturada
    if cdp.captured:
        print(f"  graphql: {cdp.captured[-1][:400]}")
        cdp.captured.clear()

    # Scroll al fondo
    cdp.eval("window.scrollTo(0, document.body.scrollHeight)")
    scroll_y = cdp.eval("window.scrollY")
    scroll_h = cdp.eval("document.body.scrollHeight")
    print(f"  scroll {scroll_y} / {scroll_h}")
    time.sleep(SLEEP_SCROLL)

    # Intentar hacer scroll al elemento "Loading more" si existe
    cdp.eval("""
(() => {
  const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
  let node, found = null;
  while (node = walker.nextNode()) {
    if (node.textContent.includes('Loading more')) {
      found = node.parentElement;
      break;
    }
  }
  if (found) {
    found.scrollIntoView({ block: 'center' });
    window.scrollBy(0, 200);
  }
})()
""")
    time.sleep(SLEEP_EXTRA)

    # Condición de salida anticipada: sin nuevos posts y sin "Loading more"
    if new_count == 0 and iteration > 8:
        has_more = cdp.eval("document.body.innerText.includes('Loading more')")
        print(f"  sin nuevos, Loading more: {has_more}")
        if not has_more and iteration > 15:
            print("No hay más contenido, terminando.")
            break

    if len(posts) >= TARGET_POSTS:
        print(f"Alcanzado objetivo de {TARGET_POSTS} posts")
        break

# ── 5. Guardar resultado final ────────────────────────────────────────────────
print(f"\nFB DONE: {len(posts)} posts totales")
output_file = OUT_DIR / "fb_slow_all.json"
output_file.write_text(
    json.dumps({"count": len(posts), "posts": posts}, indent=2, ensure_ascii=False),
    encoding="utf-8",
)
print(f"Guardado en {output_file}")
cdp.close()
