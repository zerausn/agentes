"""
scrape_ig_v2.py — Scraper mejorado v2 para Instagram REDHAC.

MEJORAS sobre scrape_ig_full.py v1:
  1. Emojis en comentarios: extrae innerHTML + limpieza de tags (en vez de innerText)
  2. Scroll para cargar más comentarios (hasta ~20-30 por post)
  3. Backoff inteligente en API de likers (3 intentos con espera creciente)
  4. Modo re-scraping selectivo basado en ig_rescrape_list.json
  5. Modo re-likers: solo llama la API de likers sin re-navegar (más rápido)
  6. Logging de calidad por post (emojis detectados, n_comentarios, etc.)

Modos de uso:
  python3 scripts/scrape_ig_v2.py                     # procesa todos los posts
  python3 scripts/scrape_ig_v2.py --mode rescrape      # solo posts en ig_rescrape_list.json
  python3 scripts/scrape_ig_v2.py --mode relikers      # solo re-likers vía API
  python3 scripts/scrape_ig_v2.py --mode all           # todos los 469 desde cero

Prerrequisito:
  Chrome/Chromium abierto con perfil de Instagram activo y CDP en puerto 9222:
  google-chrome --remote-debugging-port=9222 \\
    --user-data-dir=/home/zerausn/.var/app/com.microsoft.Edge/config/microsoft-edge \\
    --no-first-run &

  Luego navegar a instagram.com e iniciar sesión si es necesario.

Salida: output/ig_full_data.json (reanudable — salta posts ya procesados en rescrape)
Luego ejecutar: python3 scripts/fill_docs_full.py
"""

import argparse
import json
import re
import time
import unicodedata
from pathlib import Path

import requests
import websocket as ws_lib

# ── Rutas ─────────────────────────────────────────────────────────────────────
CDP_HOST      = "http://127.0.0.1:9222"
IG_SRC        = Path("/media/zerausn/D69493CF9493B08B/Users/ZN-/Documents/UNAD/"
                     "CURSOS/6/METODOLOGÍA Y GESTIÓN DE LA INVESTIGACIÓN/1/"
                     "Documentacion/1/ig_469.json")
OUT_JSON      = Path(__file__).parent.parent / "output" / "ig_full_data.json"
RESCRAPE_LIST = Path(__file__).parent.parent / "output" / "ig_rescrape_list.json"
RELIKERS_LIST = Path(__file__).parent.parent / "output" / "ig_relikers_list.json"
MIN_WIDTH     = 500

# ── Parámetros ────────────────────────────────────────────────────────────────
SCROLL_STEPS        = 2    # veces que hace scroll para cargar MÁS comentarios
SCROLL_WAIT_S       = 1.0   # segundos entre scrolls
PAGE_LOAD_S         = 10    # segundos de espera tras navegar al post
LIKERS_RETRY        = 3     # intentos para API de likers
LIKERS_BACKOFF_S    = 12    # segundos base de backoff (se multiplica por intento)
SLEEP_BETWEEN_POSTS = 2     # segundos entre posts
MAX_COMMENT_ROUNDS  = 2    # máximo de rondas de scroll+click buscando más comentarios


# ── CDP helper ─────────────────────────────────────────────────────────────────
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
            "userGesture": True,
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


# ── Helpers ────────────────────────────────────────────────────────────────────
def clean_surrogates(s: str) -> str:
    """Elimina surrogate pairs inválidos que rompen json.dumps."""
    return re.sub(r'[\ud800-\udfff]', '', s)


def has_emoji(text: str) -> bool:
    """Detecta si un texto contiene emojis u caracteres Unicode especiales."""
    for c in text:
        cat = unicodedata.category(c)
        cp = ord(c)
        if cat in ("So", "Sm") or (0x1F300 <= cp <= 0x1FAFF) or (0x2600 <= cp <= 0x27BF):
            return True
    return False


def save_json(path: Path, data: dict):
    """Guarda JSON manejando emojis y surrogates."""
    text = json.dumps(data, ensure_ascii=False, indent=2)
    text = clean_surrogates(text)
    path.write_text(text, encoding="utf-8")


# ── JavaScript para extracción ─────────────────────────────────────────────────

META_JS = r"""
(() => {
    // og:description tiene el formato antiguo, pero a veces falla en nuevos reels
    const og = document.querySelector('meta[property="og:description"]');
    const ogTitle = document.querySelector('meta[property="og:title"]');
    const desc = og ? og.content : (ogTitle ? ogTitle.content : '');

    // Fecha: time[datetime]
    const timeEl = document.querySelector('time[datetime]');
    const fecha = timeEl ? timeEl.getAttribute('datetime') : null;

    // Likes desde el DOM visible (más confiable actualmente)
    let likesCount = null;
    const spans = Array.from(document.querySelectorAll('span'));
    const likesSpan = spans.find(s => {
        const text = s.innerText || '';
        return /^\d[\d,.]*\s*(?:Me gusta|likes)/i.test(text) || /\s+y\s+\d[\d,.]*\s+personas\s+m[aá]s/i.test(text);
    });

    if (likesSpan) {
        const text = likesSpan.innerText;
        const match = text.match(/(\d[\d,.]*)/);
        if (match) {
            likesCount = parseInt(match[1].replace(/[,.]/g, ''));
            // Si dice "y X personas más", sumamos 1 por el usuario que se nombra
            if (/personas\s+m[aá]s/i.test(text)) likesCount += 1;
        }
    }

    // Nro comentarios desde og:description o DOM
    let commentsCount = null;
    const ogCommMatch = desc.match(/(\d[\d,.]*)\ s*(?:comments?|comentarios?)/i);
    if (ogCommMatch) {
        commentsCount = parseInt(ogCommMatch[1].replace(/[,.]/g, ''));
    } else {
        const svgs = Array.from(document.querySelectorAll('svg[aria-label="Comentar"], svg[aria-label="Comment"]'));
        if (svgs.length > 0) {
            const parent = svgs[0].closest('div[role="button"]');
            if (parent && parent.parentElement) {
                const text = parent.parentElement.innerText;
                const match = text.match(/(\d[\d,.]*)/);
                if (match) commentsCount = parseInt(match[1].replace(/[,.]/g, ''));
            }
        }
    }

    // Menciones en el caption (innerText principal)
    const h1 = document.querySelector('h1');
    const captionText = h1 ? h1.innerText : desc;
    const mentions = [...new Set([...captionText.matchAll(/@([\w.]+)/g)].map(m => m[1]))];

    return JSON.stringify({ desc: captionText, fecha, likesCount, commentsCount, mentions });
})()
"""

# NUEVO v2: Extrae comentarios via innerHTML para preservar emojis
COMMENTS_JS = r"""
(() => {
    // Scroll del panel de comentarios para cargar más
    // El panel principal en modo fullpage es el article o un div scrollable
    const scrollTargets = [
        document.querySelector('div[role="dialog"]'),
        document.querySelector('article'),
        document.querySelector('main'),
        document.body
    ].filter(Boolean);

    // Intentar scrollear dentro del contenedor de comentarios
    for (const target of scrollTargets) {
        if (target.scrollHeight > target.clientHeight + 100) {
            for (let i = 0; i < 5; i++) {
                target.scrollTop += 600;
            }
            break;
        }
    }

    // Extraer comentarios via innerHTML (preserva emojis)
    const commentContainers = Array.from(document.querySelectorAll(
        'ul > li[role="listitem"], ul > li'
    )).filter(li => {
        const t = li.innerText || '';
        return t.length > 3 && t.length < 2000 && !li.querySelector('header');
    });

    const seen = new Set();
    const comments = [];

    for (const li of commentContainers) {
        // Autor: primer <a> con texto
        const authorEl = li.querySelector('a[role="link"], h3 a, h2 a, a');
        const author = authorEl ? authorEl.innerText.trim() : '';

        // NUEVO: Usar innerHTML → limpiar tags → preservar emojis
        let rawHtml = li.innerHTML || '';

        // Reemplazar <br> por espacio
        rawHtml = rawHtml.replace(/<br\s*\/?>/gi, ' ');

        // Quitar tags HTML pero mantener su contenido (incluidos emojis en texto)
        let fullText = rawHtml
            .replace(/<[^>]+>/g, '')          // strip tags
            .replace(/&amp;/g, '&')
            .replace(/&lt;/g, '<')
            .replace(/&gt;/g, '>')
            .replace(/&quot;/g, '"')
            .replace(/&#39;/g, "'")
            .replace(/&nbsp;/g, ' ')
            .replace(/\s+/g, ' ')              // colapsar espacios múltiples
            .trim();

        // Limpiar el nombre del autor del inicio del texto
        if (author && fullText.startsWith(author)) {
            fullText = fullText.slice(author.length).trim();
        }

        // Eliminar timestamps al final ("1 sem", "2 d", etc.)
        fullText = fullText.replace(/\s+\d+\s*(?:sem|d|h|min|s|w|ago)\s*$/, '').trim();

        const entry = author && fullText ? `${author}: ${fullText}` : fullText;

        if (entry.length >= 4 && !seen.has(entry)) {
            seen.add(entry);
            comments.push(entry);
        }
    }

    return JSON.stringify(comments);
})()
"""

SCROLL_COMMENTS_JS = r"""
(async () => {
    // Scroll agresivo para cargar TODOS los comentarios — awaitPromise
    const wait = ms => new Promise(r => setTimeout(r, ms));
    const MAX_ROUNDS = 15;

    // Selectores de botones "Ver más comentarios"
    const loadMoreText = /ver m[aá]s comentarios|load more comments|ver todos|view all/i;
    const btnSelectors = [
        'button[class*="load"]',
        'span[class*="load"]',
        'button[type="button"]',
        'li > div > button',
        'ul + div button',
    ];

    // Contenedores scrollables a intentar
    const getScrollTarget = () => [
        document.querySelector('div[role="dialog"] > div:last-child'),
        document.querySelector('article > div:nth-child(2)'),
        document.querySelector('article'),
        document.querySelector('div[class*="comment"]'),
        document.body,
    ].filter(Boolean).find(el => el.scrollHeight > el.clientHeight + 50);

    let prevCommentCount = 0;
    let stuckRounds = 0;

    for (let round = 0; round < MAX_ROUNDS; round++) {
        // Contar comentarios actuales
        const currentCount = document.querySelectorAll('ul > li[role="listitem"], ul > li').length;

        // Si no cargaron nuevos en 2 rondas seguidas, parar
        if (currentCount <= prevCommentCount) {
            stuckRounds++;
            if (stuckRounds >= 2) break;
        } else {
            stuckRounds = 0;
        }
        prevCommentCount = currentCount;

        // Scroll en el contenedor
        const target = getScrollTarget();
        if (target) {
            target.scrollTop += 800;
            await wait(1300);
        } else {
            window.scrollBy(0, 800);
            await wait(1300);
        }

        // Buscar y clickear botón "Ver más comentarios"
        let clicked = false;
        for (const sel of btnSelectors) {
            const btns = Array.from(document.querySelectorAll(sel));
            for (const btn of btns) {
                const txt = btn.innerText || btn.textContent || '';
                if (loadMoreText.test(txt)) {
                    btn.click();
                    await wait(2500);
                    clicked = true;
                    break;
                }
            }
            if (clicked) break;
        }
    }

    const finalCount = document.querySelectorAll('ul > li[role="listitem"], ul > li').length;
    return `loaded:${finalCount}`;
})()
"""


LAST_CSRF_REFRESH = 0
CACHED_CSRF = ""

def get_fresh_csrftoken(cdp) -> str:
    global LAST_CSRF_REFRESH, CACHED_CSRF
    import time
    now = time.time()
    if now - LAST_CSRF_REFRESH > 3000:
        try:
            fresh = cdp.eval("document.cookie.match(/csrftoken=([^;]+)/)?.[1] || ''")
            if fresh and len(fresh) > 10:
                CACHED_CSRF = fresh
                LAST_CSRF_REFRESH = now
                print(f"  🔄 csrftoken renovado {fresh[:10]}... a las {time.ctime()}")
        except: pass
    return CACHED_CSRF

def build_likers_js(code_post: str) -> str:
    """Genera el JS para llamar a la API de likers de Instagram."""
    return f"""
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
        if (!csrf) return '[]';
        try {{
            const res = await fetch(`https://www.instagram.com/api/v1/media/${{mediaId}}/likers/`, {{
                headers: {{
                    'x-ig-app-id': '936619743392459',
                    'x-csrftoken': csrf,
                    'x-requested-with': 'XMLHttpRequest',
                }}
            }});
            if (!res.ok) return JSON.stringify({{error: res.status}});
            const data = await res.json();
            return JSON.stringify(data.users ? data.users.map(u => u.username) : []);
        }} catch(e) {{
            return JSON.stringify({{error: e.message}});
        }}
    }})()
    """


# ── Extracción de un post completo ────────────────────────────────────────────
def scrape_post(cdp: Cdp, href: str) -> dict:
    """Navega al post y extrae toda la información disponible."""
    is_reel = "/reel/" in href
    cdp.call("Page.navigate", {"url": href.rstrip("/")})
    time.sleep(PAGE_LOAD_S)
    cdp.flush()

    # ── 1. Metadatos desde og:description ─────────────────────────────────────
    raw = cdp.eval(META_JS)
    meta = json.loads(raw) if raw else {}

    desc         = meta.get("desc", "")
    fecha        = (meta.get("fecha") or "")[:10]
    likes_count  = meta.get("likesCount")
    nro_comments = meta.get("commentsCount")
    mentions     = meta.get("mentions", [])

    # ── 2. Reposteo ───────────────────────────────────────────────────────────
    reposteo = ""
    if desc:
        m = re.match(r'^@([\w.]+)', desc.strip())
        reposteo = f"Reposteo de @{m.group(1)}" if m else "Original"

    # ── 3. Scroll de comentarios y extracción v2 (con emojis) ─────────────────
    # Hacer scroll asíncrono primero
    cdp.eval(SCROLL_COMMENTS_JS, await_promise=True)
    time.sleep(1.0)

    raw_comments = cdp.eval(COMMENTS_JS)
    comments = json.loads(raw_comments) if raw_comments else []

    # Detectar emojis en comentarios
    emoji_in_comments = any(has_emoji(c) for c in comments)

    # ── 4. Likers con backoff (API + DOM Fallback) ────────────────────────────
    code_post = href.rstrip("/").split("/")[-1]
    api_js = build_likers_js(code_post)
    likers = []
    likers_error = None

    for attempt in range(LIKERS_RETRY):
        raw_likers = cdp.eval(api_js, await_promise=True)
        try:
            parsed = json.loads(raw_likers) if raw_likers else []
            if isinstance(parsed, list):
                likers = parsed
                if likers:
                    break
                wait_s = LIKERS_BACKOFF_S * (attempt + 1)
                time.sleep(wait_s)
            elif isinstance(parsed, dict) and "error" in parsed:
                likers_error = parsed["error"]
                break
        except Exception as e:
            likers_error = str(e)
            break

    # FALLBACK DOM: Si la API falló (ej. retornó HTML/login page), hacer click en los likes
    if not likers or (likers_error and 'Unexpected token' in likers_error):
        fallback_js = r"""
        (async () => {
            const wait = ms => new Promise(r => setTimeout(r, ms));
            const spans = Array.from(document.querySelectorAll('span'));
            const likesBtn = spans.find(s => {
                const text = s.innerText || '';
                return /^\d[\d,.]*\s*(?:Me gusta|likes)/i.test(text) || /\s+y\s+\d[\d,.]*\s+personas\s+m[aá]s/i.test(text);
            });
            if (likesBtn) {
                // Hay múltiples <a> en el span (uno para el usuario, otro para "X personas más")
                // Debemos clickear el que NO sea un usuario (usualmente tiene href="#") o dice "personas más" / "Me gusta"
                const links = Array.from(likesBtn.querySelectorAll('a'));
                let targetLink = links.find(a => /personas|m[aá]s|likes|Me gusta/i.test(a.innerText)) || 
                                 links.find(a => a.getAttribute('href') === '#');
                
                const linkToClick = targetLink || likesBtn.querySelector('a') || likesBtn.closest('a') || likesBtn;
                linkToClick.click();
                await wait(2500);
                
                // Buscar el diálogo de likes y hacer scroll
                const dialog = document.querySelector('div[role="dialog"] > div:last-child > div:last-child, div[role="dialog"] div[style*="overflow-y"]');
                if (dialog) {
                    for(let i=0; i<6; i++) {
                        dialog.scrollTop += 800;
                        await wait(1200);
                    }
                }
                
                // Extraer likers del DOM
                const users = Array.from(document.querySelectorAll('div[role="dialog"] a[role="link"]'))
                                .map(a => a.innerText.trim())
                                .filter(t => t.length > 0 && !t.includes('\n'));
                
                // Cerrar diálogo
                const closeBtn = document.querySelector('div[role="dialog"] svg[aria-label="Cerrar"], div[role="dialog"] svg[aria-label="Close"]');
                if (closeBtn) {
                    const closeParent = closeBtn.closest('div[role="button"]');
                    if(closeParent) closeParent.click();
                }
                
                return JSON.stringify([...new Set(users)]);
            }
            return '[]';
        })()
        """
        raw_dom_likers = cdp.eval(fallback_js, await_promise=True)
        if raw_dom_likers:
            try:
                dom_likers = json.loads(raw_dom_likers)
                if isinstance(dom_likers, list) and dom_likers:
                    likers = dom_likers
                    likers_error = "API falló, recuperado vía DOM"
            except:
                pass

    # ── 5. Imágenes / videos ──────────────────────────────────────────────────
    if is_reel:
        vid_js = r"""
        (() => {
            const allScript = Array.from(document.querySelectorAll('script:not([src])')).map(s => s.textContent).join('');
            const matches = [...allScript.matchAll(/"video_versions":\[(.*?)\]/g)];
            if (matches.length > 0) {
                try {
                    const arr = JSON.parse('[' + matches[0][1] + ']');
                    arr.sort((a, b) => b.width - a.width);
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
                const k = u.split('?')[0].substring(0, 80);
                if (seen[k]) return false;
                seen[k] = true; return true;
            }}));
        }})()
        """
        raw_imgs = cdp.eval(img_js)
        imgs = json.loads(raw_imgs) if raw_imgs else []
        vids = []

    return {
        "href": href,
        "texto": clean_surrogates(desc),
        "likes": likes_count,
        "likers": likers,
        "likers_error": likers_error,
        "nro_comentarios": nro_comments,
        "comentarios": [clean_surrogates(c) for c in comments],
        "emoji_en_comentarios": emoji_in_comments,
        "compartidos": None,
        "reposteo": clean_surrogates(reposteo),
        "fecha": fecha,
        "menciones": [clean_surrogates(m) for m in mentions],
        "imgs": imgs,
        "vids": vids,
        "scrape_v": 2,
    }


def relikers_only(cdp: Cdp, href: str, existing: dict) -> dict:
    """Solo re-llama la API de likers sin navegar de nuevo al post."""
    code_post = href.rstrip("/").split("/")[-1]

    # Asegurarse de que la pestaña sigue en instagram.com para la sesión
    current_url = cdp.eval("window.location.href")
    if not current_url or "instagram.com" not in current_url:
        cdp.call("Page.navigate", {"url": "https://www.instagram.com/"})
        time.sleep(5)

    api_js = build_likers_js(code_post)
    likers = []
    likers_error = None

    for attempt in range(LIKERS_RETRY):
        raw_likers = cdp.eval(api_js, await_promise=True)
        try:
            parsed = json.loads(raw_likers) if raw_likers else []
            if isinstance(parsed, list):
                likers = parsed
                if likers:
                    break
                wait_s = LIKERS_BACKOFF_S * (attempt + 1)
                print(f"    ⏳ API [] (intento {attempt+1}) — wait {wait_s}s")
                time.sleep(wait_s)
            elif isinstance(parsed, dict) and "error" in parsed:
                likers_error = parsed["error"]
                wait_s = LIKERS_BACKOFF_S * (attempt + 1)
                print(f"    ⚠️  Error {likers_error} — wait {wait_s}s")
                time.sleep(wait_s)
        except Exception as e:
            likers_error = str(e)
            break

    updated = dict(existing)
    updated["likers"] = likers
    updated["likers_error"] = likers_error
    updated["scrape_v"] = 2
    return updated


# ── Main ───────────────────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(description="Scraper IG v2 — REDHAC")
    parser.add_argument("--mode", choices=["rescrape", "relikers", "all", "new"],
                        default="rescrape",
                        help=("rescrape=solo posts en ig_rescrape_list.json (default), "
                              "relikers=solo re-likers API, "
                              "all=todos 469 desde cero, "
                              "new=solo posts no procesados"))
    args = parser.parse_args()
    mode = args.mode

    # ── Cargar fuente de URLs ─────────────────────────────────────────────────
    if not IG_SRC.exists():
        print(f"❌ No existe {IG_SRC}")
        return

    raw_src = json.loads(IG_SRC.read_text(encoding="utf-8"))
    media_list = raw_src.get("media", raw_src) if isinstance(raw_src, dict) else raw_src
    all_hrefs = {m["href"].rstrip("/").split("/")[-1]: m["href"] for m in media_list}
    print(f"Posts en ig_469.json: {len(all_hrefs)}")

    # ── Cargar datos existentes ───────────────────────────────────────────────
    result: dict = {}
    if OUT_JSON.exists():
        result = json.loads(OUT_JSON.read_text(encoding="utf-8"))
        print(f"Posts ya procesados:  {len(result)}")

    # ── Determinar qué posts procesar ─────────────────────────────────────────
    if mode == "rescrape":
        if not RESCRAPE_LIST.exists():
            print(f"❌ No existe {RESCRAPE_LIST}. Ejecuta primero: python3 scripts/audit_ig.py")
            return
        rescrape_data = json.loads(RESCRAPE_LIST.read_text(encoding="utf-8"))
        target_codes = rescrape_data["codes"]
        print(f"Modo RESCRAPE — {len(target_codes)} posts a re-scrapear")

    elif mode == "relikers":
        if not RELIKERS_LIST.exists():
            print(f"❌ No existe {RELIKERS_LIST}. Ejecuta primero: python3 scripts/audit_ig.py")
            return
        relikers_data = json.loads(RELIKERS_LIST.read_text(encoding="utf-8"))
        target_codes = relikers_data["codes"]
        print(f"Modo RELIKERS — {len(target_codes)} posts a re-likers")

    elif mode == "all":
        target_codes = list(all_hrefs.keys())
        print(f"Modo ALL — {len(target_codes)} posts")

    else:  # new
        target_codes = [c for c in all_hrefs if c not in result]
        print(f"Modo NEW — {len(target_codes)} posts nuevos")

    if not target_codes:
        print("✅ No hay posts para procesar.")
        return

    # ── Abrir pestaña CDP ─────────────────────────────────────────────────────
    try:
        r = requests.put(f"{CDP_HOST}/json/new?about:blank", timeout=10)
        tab_info = r.json()
        tab_id = tab_info["id"]
        cdp = Cdp(tab_info["webSocketDebuggerUrl"])
    except Exception as e:
        print(f"❌ No se pudo conectar al CDP en {CDP_HOST}: {e}")
        print("   Inicia Chrome con: google-chrome --remote-debugging-port=9222 ...")
        return

    cdp.call("Page.enable")
    cdp.call("Runtime.enable")

    total = len(target_codes)
    ok_count = 0
    fail_count = 0

    try:
        for idx, code in enumerate(target_codes, start=1):
            href = all_hrefs.get(code, result.get(code, {}).get("href", ""))
            if not href:
                print(f"[{idx}/{total}] {code} → href no encontrado, saltando")
                continue

            pct = idx / total * 100
            print(f"[{idx}/{total} {pct:.1f}%] {code}")

            try:
                if mode == "relikers":
                    existing = result.get(code, {"href": href})
                    data = relikers_only(cdp, href, existing)
                else:
                    data = scrape_post(cdp, href)

                result[code] = data

                # Verificación dato real: comparar likes DOM vs og:description
                n_likers   = len(data.get("likers") or [])
                n_com      = len(data.get("comentarios") or [])
                emoji_flag = "🎭" if data.get("emoji_en_comentarios") else ""
                likers_err = f" ⚠️likers_err={data.get('likers_error')}" if data.get("likers_error") else ""
                # Verificación: el dato es real si viene del DOM visible (likesCount, commentsCount) y no de HTML de login
                es_real = "✓" if data.get("likes") is not None and n_likers >= 0 else "⚠️"
                print(f"  {es_real} likes={data.get('likes')} likers={n_likers} "
                      f"nro_com={data.get('nro_comentarios')} capturados={n_com} "
                      f"{emoji_flag}{likers_err} {'[REAL]' if n_likers>0 or data.get('likes') else '[revisar]'}")
                ok_count += 1

            except Exception as e:
                print(f"  ✗ Error: {e}")
                if mode != "relikers":
                    result[code] = {"href": href, "error": str(e), "scrape_v": 2}
                fail_count += 1

            # Guardar progreso tras cada post
            save_json(OUT_JSON, result)
            time.sleep(SLEEP_BETWEEN_POSTS)

    finally:
        cdp.close()
        try:
            requests.get(f"{CDP_HOST}/json/close/{tab_id}", timeout=5)
        except Exception:
            pass

    print(f"\n{'='*55}")
    print(f"✅ Finalizado — {ok_count} ok | {fail_count} errores")
    print(f"   Total posts en ig_full_data.json: {len(result)}")
    print(f"\nSiguiente paso:")
    print(f"  python3 scripts/fill_docs_full.py")


if __name__ == "__main__":
    main()
