"""
fb_get_links.py - Obtener URLs de posts de la página de FB vía Chrome CDP
"""

import websocket
import json
import urllib.request
import time
from pathlib import Path

OUT_DIR = Path(__file__).parent.parent / "output"
OUT_DIR.mkdir(exist_ok=True)

CDP_HOST = "http://127.0.0.1:9222"
TARGET_URL_FRAGMENT = "Reddehuertosagroecologicosdecali"
ITERATIONS = 60
SLEEP_SCROLL = 5
TARGET_POSTS = 714

class Cdp:
    def __init__(self, ws_url: str):
        self.ws = websocket.create_connection(ws_url, timeout=90)
        self.seq = 0

    def call(self, method: str, params: dict = None) -> dict:
        self.seq += 1
        mid = self.seq
        self.ws.send(json.dumps({"id": mid, "method": method, "params": params or {}}))
        while True:
            payload = json.loads(self.ws.recv())
            if payload.get("id") == mid:
                if "error" in payload:
                    raise RuntimeError(f"{method}: {payload['error']}")
                return payload.get("result", {})

    def eval(self, expression: str, await_promise: bool = True):
        result = self.call("Runtime.evaluate", {
            "expression": expression,
            "awaitPromise": await_promise,
            "returnByValue": True,
            "userGesture": True,
        })
        return result.get("result", {}).get("value")

    def close(self):
        try:
            self.ws.close()
        except Exception:
            pass

def main():
    try:
        with urllib.request.urlopen(f"{CDP_HOST}/json/list", timeout=5) as resp:
            tabs = json.loads(resp.read().decode())
    except Exception as e:
        print(f"Error conectando a CDP: {e}")
        return

    fb_ws = None
    for tab in tabs:
        if TARGET_URL_FRAGMENT.lower() in tab.get("url", "").lower():
            fb_ws = tab["webSocketDebuggerUrl"]
            print("FB tab:", tab["url"])
            break

    if not fb_ws:
        print("Creando nueva pestaña para FB...")
        req = urllib.request.Request(f"{CDP_HOST}/json/new?https://www.facebook.com/Reddehuertosagroecologicosdecali", method="PUT")
        with urllib.request.urlopen(req, timeout=5) as resp:
            tab = json.loads(resp.read().decode())
            fb_ws = tab["webSocketDebuggerUrl"]

    cdp = Cdp(fb_ws)
    cdp.call("Page.enable")
    cdp.call("Runtime.enable")

    print("Navegando a REDHAC Facebook...")
    cdp.call("Page.navigate", {"url": "https://www.facebook.com/Reddehuertosagroecologicosdecali"})
    time.sleep(15)

    links_totales = set()
    out_file = OUT_DIR / "fb_links.json"

    for iteration in range(ITERATIONS):
        raw_links = cdp.eval("""
            (() => {
                const anchors = Array.from(document.querySelectorAll('a[href]'));
                const valid = [];
                for (let a of anchors) {
                    let h = a.href;
                    if (h.includes('/posts/') || h.includes('/videos/') || h.includes('/photo/') || h.includes('fbid=')) {
                        valid.push(h);
                    }
                }
                return JSON.stringify(valid);
            })()
        """)
        
        new_count = 0
        if raw_links:
            links = json.loads(raw_links)
            for link in links:
                # Limpiar query parameters inecesarios que causan duplicados
                clean_link = link.split("?")[0] if "fbid=" not in link else link.split("&__cft__")[0]
                
                # Descartar links extraños
                if "/groups/" in clean_link or "/watch/" in clean_link:
                    continue
                
                if clean_link not in links_totales:
                    links_totales.add(clean_link)
                    new_count += 1
        
        print(f"Iter {iteration:02d}: +{new_count} | Total únicos: {len(links_totales)}")
        
        # Guardar progreso
        out_file.write_text(json.dumps(list(links_totales), indent=2), encoding="utf-8")

        # Scroll al fondo
        cdp.eval("window.scrollTo(0, document.body.scrollHeight)")
        time.sleep(SLEEP_SCROLL)
        
        if len(links_totales) >= TARGET_POSTS:
            print(f"Alcanzado objetivo de links.")
            break

    print(f"DONE: {len(links_totales)} links extraídos y guardados en {out_file}")
    cdp.close()

if __name__ == "__main__":
    main()
