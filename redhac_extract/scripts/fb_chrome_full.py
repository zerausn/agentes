"""
fb_chrome_full.py - Extracción de posts Facebook REDHAC vía scroll de div interno
===================================================================================
Problema que resuelve:
  Facebook usa virtualización agresiva. Al hacer window.scrollTo simple, el feed
  no carga más allá de 6 [role="article"]. Este script intenta scrollear el
  div interno del feed (el que tiene hasFeed / scrollHeight > 1500px).

Complementa fb_slow_60.py (que usa body.innerText split). Este script es el
método alternativo con scroll de div interno + click "Ver más".

Salida (en carpeta output/):
  - fb_chrome_progress.json  → progreso incremental
  - fb_chrome_all.json       → posts extraídos
  - fb_about.txt             → texto de la sección "Información" de la página

Requisitos:
  pip install websocket-client requests

Uso:
  # 1. Abrir Chrome con perfil Edge y CDP:
  google-chrome --remote-debugging-port=9222 \\
    --user-data-dir=/home/zerausn/.var/app/com.microsoft.Edge/config/microsoft-edge \\
    --no-first-run &
  # 2. Abrir manualmente: https://www.facebook.com/Reddehuertosagroecologicosdecali
  # 3. Ejecutar:
  python3 scripts/fb_chrome_full.py

Nota:
  Por la virtualización de Facebook, este script obtiene menos posts que
  fb_slow_60.py. Para 714 posts se recomienda fb_slow_60.py (333 raw confirmados).
"""

import json
import time
import urllib.request
import websocket
import re
import requests
from pathlib import Path

# ── Carpeta de salida ─────────────────────────────────────────────────────────
OUT_DIR = Path(__file__).parent.parent / "output"
OUT_DIR.mkdir(exist_ok=True)

CDP_HOST = "http://127.0.0.1:9222"
TARGET_URL_FRAGMENT = "Reddehuertosagroecologicosdecali"
ITERATIONS = 3
SLEEP_SCROLL = 4     # segundos entre scroll y extracción
MAX_POSTS = 150      # límite conservador para este método


class Cdp:
    """Cliente mínimo del Chrome DevTools Protocol via WebSocket."""

    def __init__(self, ws_url: str):
        self.ws = websocket.create_connection(ws_url, timeout=60)
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

    def eval(self, expression: str, await_promise: bool = True):
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


# ── 1. Encontrar (o crear) pestaña de Facebook ───────────────────────────────
with urllib.request.urlopen(f"{CDP_HOST}/json/list", timeout=5) as resp:
    tabs = json.loads(resp.read().decode())

fb_ws = None
for tab in tabs:
    if TARGET_URL_FRAGMENT in tab.get("url", "") and tab.get("type") == "page":
        fb_ws = tab["webSocketDebuggerUrl"]
        print("FB Chrome tab:", tab["url"])
        break

if not fb_ws:
    # Crear pestaña nueva navigando directo
    r = requests.put(
        f"{CDP_HOST}/json/new?https://www.facebook.com/Reddehuertosagroecologicosdecali",
        timeout=10,
    )
    fb_ws = r.json()["webSocketDebuggerUrl"]
    print("Pestaña FB creada")

cdp = Cdp(fb_ws)
cdp.call("Page.enable")
cdp.call("Runtime.enable")

# ── 2. Navegar y leer header ─────────────────────────────────────────────────
print("Navegando a página principal de REDHAC FB...")
cdp.call("Page.navigate", {"url": "https://www.facebook.com/Reddehuertosagroecologicosdecali"})
time.sleep(10)

current_url = cdp.eval("location.href")
print("URL actual:", current_url)

header_raw = cdp.eval("""
(() => {
  const txt = document.body.innerText.replace(/\u034f/g, '');
  const m = txt.match(/([0-9.,]+)\s*(mil)?\s*seguidores/i);
  const followers = m ? m[0] : '1549 seguidores';
  const contact = txt.match(/[a-z0-9._%+-]+@[a-z0-9.-]+\.[a-z]{2,}/i)?.[0]
    || 'redhuertosagroecologicoscali@gmail.com';
  const cat = txt.match(/Página · [^\n]+/)?.[0] || 'Agricultura';
  const addr = txt.match(/Calle[^\n]+/)?.[0] || 'Calle13, Santiago de Cali, Colombia, 760032';
  return JSON.stringify({ followers, contact, category: cat, address: addr, title: document.title, url: location.href });
})()
""")
print("Header:", header_raw)
header_obj = json.loads(header_raw) if header_raw else {}

# ── 3. SCROLL con div interno + body.innerText ───────────────────────────────
posts: list[str] = []
seen: set[str] = set()

for iteration in range(ITERATIONS):
    # Intentar scrollear el div interno del feed (el que tiene scrollHeight > 1500)
    scroll_result = cdp.eval("""
(() => {
  const allDivs = Array.from(document.querySelectorAll('div'));
  const scrollables = allDivs.filter(
    d => d.scrollHeight > d.clientHeight + 80 && d.scrollHeight > 1500
  );
  // Buscar el div que contiene posts de REDHAC
  let target = null;
  let maxSH = 0;
  for (const d of scrollables) {
    const txt = d.innerText || '';
    if (txt.includes('Red De Huertos') && d.scrollHeight > maxSH) {
      maxSH = d.scrollHeight;
      target = d;
    }
  }
  // Fallback: el div con mayor scrollHeight
  if (!target && scrollables.length > 0) {
    target = scrollables.reduce((a, b) => a.scrollHeight > b.scrollHeight ? a : b, scrollables[0]);
  }
  if (target) {
    const before = target.scrollTop;
    target.scrollTop = target.scrollHeight;
    window.scrollTo(0, document.body.scrollHeight);
    return JSON.stringify({
      found: true, before, after: target.scrollTop,
      sh: target.scrollHeight, ch: target.clientHeight,
      bodyLen: document.body.innerText.length,
      articles: document.querySelectorAll('[role="article"]').length,
    });
  } else {
    window.scrollTo(0, document.body.scrollHeight);
    return JSON.stringify({
      found: false,
      windowSH: document.body.scrollHeight,
      bodyLen: document.body.innerText.length,
      articles: document.querySelectorAll('[role="article"]').length,
    });
  }
})()
""")
    print(f"Iter {iteration:02d} scroll:", scroll_result)
    time.sleep(SLEEP_SCROLL)

    # Extraer posts del body.innerText
    body = cdp.eval("document.body.innerText")
    if not body:
        continue

    body_clean = body.replace("\u034f", "")
    parts = body_clean.split("Red De Huertos Agroecologicos Cali")
    new_count = 0

    for part in parts[1:]:
        lines = [ln.strip() for ln in part.split("\n") if ln.strip()]
        if len(lines) >= 2 and len(lines[0]) < 70:
            content = " ".join(lines[1:])
        elif lines:
            content = " ".join(lines)
        else:
            content = ""

        content = re.sub(r'\s+', ' ', content).strip()
        if len(content) < 50:
            continue
        # Filtrar footer de privacidad
        if "Privacidad" in content and "Condiciones" in content and len(content) < 900:
            continue

        key = content[:400]
        if key not in seen:
            seen.add(key)
            posts.append(content)
            new_count += 1

    art_count = cdp.eval("document.querySelectorAll('[role=\"article\"]').length")
    print(f"  +{new_count} nuevos | total {len(posts)} | bodyLen {len(body)} | articles {art_count}")

    # Guardar progreso
    progress_file = OUT_DIR / "fb_chrome_progress.json"
    progress_file.write_text(
        json.dumps({"header": header_obj, "count": len(posts), "posts": posts}, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    # Sin nuevos: intentar clic en "Ver más publicaciones"
    if new_count == 0 and iteration > 5:
        if iteration > 10:
            print("  sin nuevos → intentando clic 'Ver más'...")
            clicked = cdp.eval("""
(() => {
  const btns = Array.from(document.querySelectorAll('[role="button"], a')).filter(
    b => b.innerText && (
      b.innerText.includes('Ver más') ||
      b.innerText.includes('See more') ||
      b.innerText.includes('Mostrar más')
    )
  );
  let count = 0;
  for (const b of btns.slice(0, 3)) {
    try { b.click(); count++; } catch (e) {}
  }
  return count;
})()
""")
            print(f"  clics Ver más: {clicked}")
            time.sleep(3)

            body2 = cdp.eval("document.body.innerText")
            if body2 and len(body2) == len(body):
                print("  body no creció → sin más contenido")
                if iteration > 15:
                    break

    if len(posts) >= MAX_POSTS:
        print(f"Límite de {MAX_POSTS} posts alcanzado")
        break

# ── 4. Guardar resultado final ────────────────────────────────────────────────
print(f"\nFB DONE: {len(posts)} posts")
output_file = OUT_DIR / "fb_chrome_all.json"
output_file.write_text(
    json.dumps({"header": header_obj, "posts": posts}, indent=2, ensure_ascii=False),
    encoding="utf-8",
)
print(f"Guardado en {output_file}")

# ── 5. Extra: Leer sección "Información" ─────────────────────────────────────
about_click = cdp.eval("""
(() => {
  const infoTab = Array.from(document.querySelectorAll('a'))
    .find(a => a.innerText.trim() === 'Información');
  if (infoTab) { infoTab.click(); return 'clicked'; }
  return 'not found';
})()
""")
print("About click:", about_click)
time.sleep(4)

about_text = cdp.eval("document.body.innerText.slice(0, 4000)") or ""
print("About snippet:", about_text[:500])
about_file = OUT_DIR / "fb_about.txt"
about_file.write_text(about_text, encoding="utf-8")
print(f"About guardado en {about_file}")

cdp.close()
