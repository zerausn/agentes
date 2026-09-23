"""
scrape_fb_full.py - Extracción por post para Facebook
"""

import json
import time
import re
import requests
import websocket as ws_lib
from pathlib import Path

CDP_HOST  = "http://127.0.0.1:9222"
FB_LINKS  = Path(__file__).parent.parent / "output" / "fb_links.json"
OUT_JSON  = Path(__file__).parent.parent / "output" / "fb_full_data.json"
MIN_WIDTH = 300

class Cdp:
    def __init__(self, ws_url: str):
        self.ws = ws_lib.create_connection(ws_url, timeout=30)
        self.seq = 0

    def call(self, method: str, params: dict = None) -> dict:
        self.seq += 1
        mid = self.seq
        self.ws.send(json.dumps({"id": mid, "method": method, "params": params or {}}))
        while True:
            d = json.loads(self.ws.recv())
            if d.get("id") == mid:
                return d.get("result", {})

    def eval(self, js: str, await_promise=False) -> object:
        r = self.call("Runtime.evaluate", {
            "expression": js,
            "awaitPromise": await_promise,
            "returnByValue": True,
        })
        return r.get("result", {}).get("value")

    def close(self):
        try:
            self.ws.close()
        except Exception:
            pass

def scrape_fb_post(cdp: Cdp, href: str) -> dict:
    cdp.call("Page.navigate", {"url": href})
    time.sleep(12) # Dar tiempo a FB para cargar el DOM y modales

    # Bajar un poco para cargar comentarios
    cdp.eval("window.scrollBy(0, 500)")
    time.sleep(3)

    js_extract = f"""
    (() => {{
        // 1. Texto principal
        let texto = "";
        const messageElements = Array.from(document.querySelectorAll('div[data-ad-comet-preview="message"]'));
        if (messageElements.length > 0) {{
            texto = messageElements[0].innerText;
        }} else {{
            // Fallback: tratar de buscar texto largo
            const els = Array.from(document.querySelectorAll('div[dir="auto"]')).filter(e => e.innerText.length > 50);
            if(els.length > 0) texto = els[0].innerText;
        }}

        // 2. Likes
        let likes = 0;
        // Facebook suele usar aria-labels o spans con un formato específico
        const likeSpans = Array.from(document.querySelectorAll('span')).filter(s => 
            s.innerText && /^\d+$/.test(s.innerText.replace(/[,.]/g, '')) || 
            (s.innerText && s.innerText.toLowerCase().includes('mil'))
        );
        // Heurística muy básica, se refinará
        for (let s of likeSpans) {{
            let val = parseInt(s.innerText.replace(/[,.]/g, ''));
            if (!isNaN(val) && val > likes && val < 100000) likes = val;
        }}

        // 3. Comentarios
        let comentarios = [];
        const commEls = Array.from(document.querySelectorAll('div[role="article"]'));
        for (let el of commEls) {{
            if (el.innerText.length > 3 && el.innerText.length < 5000) {{
                // Limpiar estructura (autor\\ntexto\\n...)
                let parts = el.innerText.split('\\n');
                if (parts.length > 1) {{
                    comentarios.push(parts[0] + ": " + parts.slice(1).join(" "));
                }} else {{
                    comentarios.push(el.innerText);
                }}
            }}
        }}
        // Limitar los comentarios válidos
        comentarios = comentarios.filter(c => !c.includes('Me gusta') && !c.includes('Responder') && !c.includes('Compartir'));

        // 4. Medios
        const imgs = Array.from(document.querySelectorAll('img'))
            .filter(i => i.naturalWidth >= {MIN_WIDTH} && i.src.includes('scontent'))
            .map(i => i.src);
            
        const vids = Array.from(document.querySelectorAll('video'))
            .map(v => v.src || (v.querySelector('source') ? v.querySelector('source').src : ''));

        return JSON.stringify({{ texto, likes, comentarios, imgs, vids }});
    }})()
    """
    raw = cdp.eval(js_extract)
    data = json.loads(raw) if raw else {}

    return {
        "href": href,
        "texto": data.get("texto", ""),
        "likes": data.get("likes", 0),
        "likers": [], # Postergado según plan
        "nro_comentarios": len(data.get("comentarios", [])),
        "comentarios": data.get("comentarios", []),
        "compartidos": None,
        "reposteo": "",
        "fecha": "",
        "menciones": [],
        "imgs": list(set(data.get("imgs", []))),
        "vids": list(set([v for v in data.get("vids", []) if v.startswith("http")])),
    }

def main():
    if not FB_LINKS.exists():
        print(f"Error: {FB_LINKS} no existe.")
        return

    links = json.loads(FB_LINKS.read_text(encoding="utf-8"))
    print(f"Total posts a scrapear: {len(links)}")

    result = {}
    if OUT_JSON.exists():
        result = json.loads(OUT_JSON.read_text(encoding="utf-8"))
        print(f"Retomando: {len(result)} posts ya procesados.")

    r = requests.put(f"{CDP_HOST}/json/new?about:blank", timeout=10)
    tab_id = r.json()["id"]
    cdp = Cdp(r.json()["webSocketDebuggerUrl"])
    cdp.call("Page.enable")
    cdp.call("Runtime.enable")

    for idx, href in enumerate(links, start=1):
        code = href.split("?")[0].rstrip("/").split("/")[-1]
        if not code or code == "posts": 
            code = str(idx) # Fallback id

        if code in result:
            print(f"[{idx}/{len(links)}] {code} → ya procesado.")
            continue

        print(f"[{idx}/{len(links)}] Scraping {href}")
        try:
            data = scrape_fb_post(cdp, href)
            result[code] = data
            print(f"  ✓ likes={data['likes']} comentarios={data['nro_comentarios']} imgs={len(data['imgs'])} vids={len(data['vids'])}")
        except Exception as e:
            print(f"  ✗ Error: {e}")
            result[code] = {"href": href, "error": str(e)}

        OUT_JSON.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")

    cdp.close()
    requests.get(f"{CDP_HOST}/json/close/{tab_id}", timeout=5)
    print(f"\\n✓ Extracción completa en {OUT_JSON}")

if __name__ == "__main__":
    main()
