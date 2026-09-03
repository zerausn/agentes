"""
scrape_ig_full.py — Extracción COMPLETA de todos los 469 posts de Instagram.

Por cada post extrae:
  - Texto completo
  - Total Likes
  - Quien dio Like (lista de usuarios)
  - Nro Comentarios
  - Comentarios (autor: texto)
  - Fecha
  - Menciones (@usuario en caption)
  - Imagen(es) / Video URL(s)
  - Link Post
  - Compartidos (si Instagram lo expone; si no → vacío)
  - Reposteo (si el caption menciona @usuario al inicio → "Sí - original @...")

Salida: output/ig_full_data.json  (reanudable: salta posts ya procesados)
Luego ejecutar fill_docs_full.py para volcar todo al Excel y al .md

Tiempo estimado: 469 posts × ~15s = ~2 horas
"""

import json
import time
import re
import requests
import websocket as ws_lib
from pathlib import Path

# ── Rutas ────────────────────────────────────────────────────────────────────
CDP_HOST  = "http://127.0.0.1:9222"
IG_SRC    = Path("/media/zerausn/D69493CF9493B08B/Users/ZN-/Documents/UNAD/"
                 "CURSOS/6/METODOLOGÍA Y GESTIÓN DE LA INVESTIGACIÓN/1/"
                 "Documentacion/1/ig_469.json")
OUT_JSON  = Path(__file__).parent.parent / "output" / "ig_full_data.json"
MIN_WIDTH = 500


# ── CDP helper ────────────────────────────────────────────────────────────────
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

    def click_xy(self, x: float, y: float):
        for t in ("mousePressed", "mouseReleased"):
            self.call("Input.dispatchMouseEvent",
                      {"type": t, "x": x, "y": y, "button": "left", "clickCount": 1})

    def flush(self, timeout=0.5):
        self.ws.settimeout(timeout)
        while True:
            try:
                self.ws.recv()
            except Exception:
                break
        self.ws.settimeout(30)

    def close(self):
        try:
            self.ws.close()
        except Exception:
            pass


# ── Extracción de un post ─────────────────────────────────────────────────────
def scrape_post(cdp: Cdp, href: str) -> dict:
    is_reel = "/reel/" in href
    cdp.call("Page.navigate", {"url": href.rstrip("/")})
    time.sleep(8)
    cdp.flush()

    # ── 1. Metadatos básicos del DOM ──────────────────────────────────────────
    meta_js = r"""
    (() => {
        // og:description tiene el formato: "X likes, Y comments - @usuario: caption"
        const og = document.querySelector('meta[property="og:description"]');
        const ogTitle = document.querySelector('meta[property="og:title"]');
        const desc = og ? og.content : (ogTitle ? ogTitle.content : '');

        // Fecha: time[datetime]
        const timeEl = document.querySelector('time[datetime]');
        const fecha = timeEl ? timeEl.getAttribute('datetime') : null;

        // ── Likes: extraer de og:description PRIMERO (más confiable)
        //    Formatos: "107 likes", "1,234 likes", "107 Me gusta"
        let likesCount = null;
        const ogLikesMatch = desc.match(/(\d[\d,.]*)\s*(?:likes?|Me gusta)/i);
        if (ogLikesMatch) {
            likesCount = parseInt(ogLikesMatch[1].replace(/[,.]/g, ''));
        } else {
            // Fallback: buscar en bodyText
            const bodyText = document.body.innerText;
            const bodyMatch = bodyText.match(/(\d[\d,.]*)\s*(?:likes?|Me gusta)/i);
            if (bodyMatch) likesCount = parseInt(bodyMatch[1].replace(/[,.]/g, ''));
        }

        // ── Comentarios: extraer de og:description PRIMERO
        //    Formato: "107 likes, 5 comments"
        let commentsCount = null;
        const ogCommMatch = desc.match(/(\d[\d,.]*)\s*(?:comments?|comentarios?)/i);
        if (ogCommMatch) {
            commentsCount = parseInt(ogCommMatch[1].replace(/[,.]/g, ''));
        } else {
            const bodyText2 = document.body.innerText;
            const bodyCommMatch = bodyText2.match(/(\d[\d,.]*)\s*(?:comments?|comentarios?)/i);
            if (bodyCommMatch) commentsCount = parseInt(bodyCommMatch[1].replace(/[,.]/g, ''));
        }

        // ── Menciones: @usuario en el caption (de og:description)
        const mentions = [...new Set([...desc.matchAll(/@([\w.]+)/g)].map(m => m[1]))];

        // ── Comentarios visibles en el DOM (los que cargó la página)
        const commentEls = Array.from(document.querySelectorAll(
            'ul li span, [role="listitem"] span, article span'
        )).filter(el => {
            const t = el.innerText || '';
            return t.length > 3 && t.length < 500 && !el.closest('button') && !el.closest('header');
        });
        const comments = commentEls.slice(0, 40).map(el => {
            const li = el.closest('li,[role="listitem"]');
            const authorEl = li ? li.querySelector('a[role="link"],a') : null;
            const author = authorEl ? authorEl.innerText.trim() : '';
            const text = el.innerText.trim().substring(0, 300);
            return author ? `${author}: ${text}` : text;
        }).filter((v, i, a) => v.length > 3 && a.indexOf(v) === i);

        return JSON.stringify({ desc, fecha, likesCount, commentsCount, mentions, comments });
    })()
    """
    raw = cdp.eval(meta_js)
    meta = json.loads(raw) if raw else {}

    desc         = meta.get("desc", "")
    fecha        = (meta.get("fecha") or "")[:10]
    likes_count  = meta.get("likesCount")
    nro_comments = meta.get("commentsCount")
    mentions     = meta.get("mentions", [])
    comments     = meta.get("comments", [])

    # ── 2. Reposteo (heurística: si el caption empieza con @usuario) ──────────
    reposteo = ""
    if desc:
        m = re.match(r'^@([\w.]+)', desc.strip())
        if m:
            reposteo = f"Reposteo de @{m.group(1)}"
        else:
            reposteo = "Original"

    # ── 3. Likers: API nativa de Instagram (siempre se llama, sin depender del count)
    code_post = href.rstrip("/").split("/")[-1]
    api_js = f"""
    (async () => {{
        function shortcodeToMediaId(shortcode) {{
            const alphabet = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_';
            let id = 0n;
            for (let i = 0; i < shortcode.length; i++) {{
                id = (id * 64n) + BigInt(alphabet.indexOf(shortcode[i]));
            }}
            return id.toString();
        }}
        const mediaId = shortcodeToMediaId('{code_post}');
        const csrfMatch = document.cookie.match(/csrftoken=([^;]+)/);
        const csrf = csrfMatch ? csrfMatch[1] : '';
        if(!csrf) return '[]';
        try {{
            const res = await fetch(`https://www.instagram.com/api/v1/media/${{mediaId}}/likers/`, {{
                headers: {{ 'x-ig-app-id': '936619743392459', 'x-csrftoken': csrf }}
            }});
            const data = await res.json();
            return JSON.stringify(data.users ? data.users.map(u => u.username) : []);
        }} catch(e) {{
            return '[]';
        }}
    }})()
    """
    raw_likers = cdp.eval(api_js, await_promise=True)
    likers = json.loads(raw_likers) if raw_likers else []

    # ── 4. Imágenes / videos ──────────────────────────────────────────────────
    if is_reel:
        vid_js = r"""
        (() => {
            const allScript = Array.from(document.querySelectorAll('script:not([src])')).map(s => s.textContent).join('');
            const matches = [...allScript.matchAll(/"video_versions":\[(.*?)\]/g)];
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
        vid_url = cdp.eval(vid_js)
        imgs, vids = [], ([vid_url] if vid_url else [])
    else:
        img_js = f"""
        (() => {{
            const imgs = Array.from(document.querySelectorAll('img'))
                .filter(i => i.naturalWidth >= {MIN_WIDTH} && !i.closest('a'))
                .map(i => i.src);
            const seen = {{}};
            return JSON.stringify(imgs.filter(u => {{
                const k = u.split('?')[0].substring(0,80);
                if(seen[k]) return false;
                seen[k] = true; return true;
            }}));
        }})()
        """
        raw_imgs = cdp.eval(img_js)
        imgs = json.loads(raw_imgs) if raw_imgs else []
        vids = []

    return {
        "href": href,
        "texto": desc,
        "likes": likes_count,
        "likers": likers,
        "nro_comentarios": nro_comments,
        "comentarios": comments,
        "compartidos": None,   # Instagram no lo expone públicamente
        "reposteo": reposteo,
        "fecha": fecha,
        "menciones": mentions,
        "imgs": imgs,
        "vids": vids,
    }


# ── Main ──────────────────────────────────────────────────────────────────────
def main():
    if not IG_SRC.exists():
        print(f"Error: no existe {IG_SRC}")
        return

    raw = json.loads(IG_SRC.read_text(encoding="utf-8"))
    media = raw.get("media", raw) if isinstance(raw, dict) else raw
    print(f"Total posts: {len(media)}")

    # Cargar progreso anterior
    result: dict = {}
    if OUT_JSON.exists():
        result = json.loads(OUT_JSON.read_text(encoding="utf-8"))
        print(f"Retomando: {len(result)} posts ya procesados.")

    # Abrir pestaña CDP reutilizable
    r = requests.put(f"{CDP_HOST}/json/new?about:blank", timeout=10)
    tab_id = r.json()["id"]
    cdp = Cdp(r.json()["webSocketDebuggerUrl"])
    cdp.call("Page.enable")
    cdp.call("Runtime.enable")

    total = len(media)
    for idx, m in enumerate(media, start=1):
        href = m["href"]
        code = href.rstrip("/").split("/")[-1]

        if code in result:
            print(f"[{idx}/{total}] {code} → ya procesado.")
            continue

        print(f"[{idx}/{total}] {code}  {href}")
        try:
            data = scrape_post(cdp, href)
            result[code] = data
            n_imgs = len(data["imgs"])
            n_vids = len(data["vids"])
            n_likers = len(data["likers"])
            print(f"  ✓ likes={data['likes']} likers={n_likers} comentarios={data['nro_comentarios']} imgs={n_imgs} vids={n_vids}")
        except Exception as e:
            print(f"  ✗ Error: {e}")
            result[code] = {"href": href, "error": str(e)}

        # Guardar progreso tras cada post
        OUT_JSON.write_text(
            json.dumps(result, ensure_ascii=False, indent=2),
            encoding="utf-8"
        )

    cdp.close()
    requests.get(f"{CDP_HOST}/json/close/{tab_id}", timeout=5)
    print(f"\n✓ Extracción completa. {len(result)} posts en {OUT_JSON}")


if __name__ == "__main__":
    main()
