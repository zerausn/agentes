import argparse
import json
import logging
import os
import re
import sys
import time
import unicodedata
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from meta_uploader import (
    FB_PAGE_ID,
    META_FB_PAGE_TOKEN,
    IG_USER_ID,
    get_facebook_page_feed,
    get_instagram_library_batch,
    wait_for_ig_container,
    wait_for_ig_container_upload_ready,
    publish_ig_container,
    check_ig_publish_limit,
    ensure_ig_compatibility,
    probe_video,
)

BASE_DIR = Path(__file__).resolve().parent
HISTORY_FILE = BASE_DIR / "crosspost_history.json"
DEDUPE_REGISTRY_FILE = BASE_DIR / "crosspost_dedupe_registry.json"
CAPTION_SIGNATURE = "\n\n#PW\nSíguenos también en Facebook"
# Número máximo de fallos consecutivos antes de marcar un post como procesado (evita reintentos infinitos)
MAX_CONSECUTIVE_FAILURES = 3
FAILURE_COUNTS_FILE = BASE_DIR / "crosspost_failure_counts.json"
# `_teaser_<n>` es una derivada distinta del mismo video fuente. El lookahead
# deja que el patron capture el stem aunque el nombre venga pegado al sufijo
# (ej: 20260429_185945_teaser_14), sin incluir el sufijo en el stem.
STEM_PATTERNS = (
    re.compile(r"\b\d{8}[\s_-]\d{6}(?:_\d+)?(?=$|[^\w]|_teaser_\d+)", re.IGNORECASE),
    re.compile(r"\b\d{8}[-_]\d{4}(?=$|[^\w]|_teaser_\d+)", re.IGNORECASE),
    re.compile(r"\bvid-\d{8}-wa\d+(?=$|[^\w]|_teaser_\d+)", re.IGNORECASE),
)
# Prefijo de marca al inicio del caption (#PW | ..., #SW | ..., #GW | ...).
# Se elimina para que el mismo teaser publicado en varias paginas comparta
# la clave `text:` y se deduplique entre paginas.
PAGE_PREFIX_RE = re.compile(r"^\s*#(?:pw|sw|gw|sc)\s*\|\s*", re.IGNORECASE)
PW_PREFIX_RE = re.compile(r"^\s*pw\s*\|\s*\d{4}-\d{2}-\d{2}\s*\|\s*", re.IGNORECASE)
# Solo se eliminan etiquetas de marca/calidad. `#full` y `#teaser` se
# conservan porque distinguen derivadas del mismo video fuente.
NOISE_TOKEN_RE = re.compile(r"(?i)\s*#(?:pw|sw|gw|sc|hq|pc|p)\b")
TEASER_TAIL_RE = re.compile(r"^[)\]\s]*_?teaser[ _-]*(\d+)\b", re.IGNORECASE)
UNNUMBERED_TEASER_RE = re.compile(r"(?i)#teaser\b")
MULTISPACE_RE = re.compile(r"\s+")

# Codigos internos del ciclo. `main()` los traduce a codigos de salida del
# proceso (0 publicado, 2 sin candidatos, 3 fallo de publicacion, 1 error).
CYCLE_PUBLISHED = 1
CYCLE_NO_CANDIDATE = 2
CYCLE_PUBLISH_FAILED = 3

# Páginas de Facebook → Instagram
# Cada entrada: (page_id, page_token, page_name)
FB_PAGES = [
    (
        os.environ.get("META_FB_PAGE_ID", FB_PAGE_ID),
        os.environ.get("META_FB_PAGE_TOKEN", META_FB_PAGE_TOKEN),
        "Performatic Writings Cali",
    ),
    (
        os.environ.get("META_FB_PAGE_ID_SHIRABYOSHI", os.environ.get("META_FB_PAGE_ID_TEASER", "1347014641828725")),
        # Busca META_FB_PAGE_TOKEN_SHIRABYOSHI (nombre en .env) con fallback a
        # META_FB_PAGE_TOKEN_TEASER (nombre legacy en .agentes_termux_env)
        os.environ.get("META_FB_PAGE_TOKEN_SHIRABYOSHI") or os.environ.get("META_FB_PAGE_TOKEN_TEASER", ""),
        "Shirabyoshi Writings",
    ),
    (
        os.environ.get("META_FB_PAGE_ID_SEANCHAI", "824642984061807"),
        os.environ.get("META_FB_PAGE_TOKEN_SEANCHAI", ""),
        "Seanchai Writings",
    ),
    (
        os.environ.get("META_FB_PAGE_ID_GHAWAZEE", "1288381367700799"),
        os.environ.get("META_FB_PAGE_TOKEN_GHAWAZEE", ""),
        "Ghawazee Writings",
    ),
]


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - [VIGIA-4.0] - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler(BASE_DIR / "fb_to_ig_vigia.log", encoding="utf-8"),
        logging.StreamHandler(),
    ],
)


# ─── Historial / Registro ────────────────────────────────────────────────────

def load_history():
    if not HISTORY_FILE.exists():
        return set()
    try:
        with open(HISTORY_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            return set(data) if isinstance(data, list) else set()
    except Exception as e:
        logging.warning("No se pudo leer el historial: %s", e)
        return set()


DEEP_CURSORS_FILE = BASE_DIR / "crosspost_deep_cursors.json"

def load_dedupe_registry():
    if not DEDUPE_REGISTRY_FILE.exists():
        return {"processed_post_ids": set(), "processed_keys": set()}
    try:
        with open(DEDUPE_REGISTRY_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception as e:
        logging.warning("No se pudo leer el registro de deduplicacion: %s", e)
        return {"processed_post_ids": set(), "processed_keys": set()}
    if isinstance(data, list):
        return {
            "processed_post_ids": set(),
            "processed_keys": {_normalize_registry_key(key) for key in data},
        }
    if not isinstance(data, dict):
        return {"processed_post_ids": set(), "processed_keys": set()}
    return {
        "processed_post_ids": set(data.get("processed_post_ids") or []),
        "processed_keys": {
            _normalize_registry_key(key)
            for key in (data.get("processed_keys") or [])
        },
    }


def save_history(history):
    try:
        with open(HISTORY_FILE, "w", encoding="utf-8") as f:
            json.dump(list(history), f, indent=2)
    except Exception as e:
        logging.error("Error al guardar historial: %s", e)


def save_dedupe_registry(registry):
    payload = {
        "processed_post_ids": sorted(registry.get("processed_post_ids") or []),
        "processed_keys": sorted(registry.get("processed_keys") or []),
    }
    try:
        with open(DEDUPE_REGISTRY_FILE, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2, ensure_ascii=False)
    except Exception as e:
        logging.error("Error al guardar registro de deduplicacion: %s", e)


def load_failure_counts():
    if not FAILURE_COUNTS_FILE.exists():
        return {}
    try:
        with open(FAILURE_COUNTS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        logging.warning("No se pudo leer el registro de fallos: %s", e)
        return {}


def save_failure_counts(counts):
    try:
        with open(FAILURE_COUNTS_FILE, "w", encoding="utf-8") as f:
            json.dump(counts, f, indent=2)
    except Exception as e:
        logging.error("Error al guardar conteo de fallos: %s", e)


def register_processed_post(history, registry, post_id, content_keys=None, remember_keys=True):
    if post_id:
        history.add(post_id)
        registry["processed_post_ids"].add(post_id)
        save_history(history)
    if remember_keys and content_keys:
        registry["processed_keys"].update(content_keys)
    save_dedupe_registry(registry)


# ─── Normalización y deduplicación ───────────────────────────────────────────

def _strip_accents(value):
    normalized = unicodedata.normalize("NFKD", str(value or ""))
    return "".join(ch for ch in normalized if not unicodedata.combining(ch))


def _first_nonempty_line(value):
    lines = [line.strip() for line in str(value or "").splitlines() if line.strip()]
    return lines[0] if lines else ""


def _normalize_marker(value):
    raw = _strip_accents(value or "")
    raw = raw.replace(_strip_accents(CAPTION_SIGNATURE), "")
    text = _first_nonempty_line(raw)
    text = PAGE_PREFIX_RE.sub("", text)
    text = PW_PREFIX_RE.sub("", text)
    text = NOISE_TOKEN_RE.sub("", text)
    text = MULTISPACE_RE.sub(" ", text).strip(" |-_").lower()
    return text


def _normalize_stem(value):
    stem = _strip_accents(value or "").strip().lower()
    stem = re.sub(r"[\s-]+", "_", stem)
    return stem


def _normalize_registry_key(key):
    """Normaliza claves `text:` viejas para que el prefijo de pagina no rompa
    la deduplicacion entre paginas. Las claves `stem:` viejas se conservan en
    el registro pero ya no se generan (ver _extract_content_identities)."""
    if not isinstance(key, str) or not key.startswith("text:"):
        return key
    normalized = _normalize_marker(key[len("text:"):])
    return f"text:{normalized}" if normalized else key


def _extract_content_identities(raw):
    """Identidades de contenido independientes de la pagina.

    - Video completo: `<stem>`
    - Teaser numerado: `<stem>_teaser_<n>` (misma derivada en cualquier pagina)
    - Teaser sin numero: `<stem>_teaser` (no bloquea al video completo)
    """
    normalized = _strip_accents(str(raw or ""))
    unnumbered_teaser = bool(UNNUMBERED_TEASER_RE.search(_first_nonempty_line(normalized)))
    identities = set()
    for pattern in STEM_PATTERNS:
        for match in pattern.finditer(normalized):
            stem = _normalize_stem(match.group(0))
            if not stem:
                continue
            tail = normalized[match.end():match.end() + 24]
            teaser_match = TEASER_TAIL_RE.match(tail)
            if teaser_match:
                identities.add(f"{stem}_teaser_{int(teaser_match.group(1))}")
            elif unnumbered_teaser:
                identities.add(f"{stem}_teaser")
            else:
                identities.add(stem)
    return identities


def extract_content_keys(text):
    raw = str(text or "")
    keys = set()
    marker = _normalize_marker(raw)
    if marker:
        keys.add(f"text:{marker}")
    for identity in _extract_content_identities(raw):
        keys.add(f"content:{identity}")
    return keys


def build_catalog_key_index(catalog):
    keys = set()
    for entry in catalog or []:
        keys.update(extract_content_keys(entry))
    return keys


def find_duplicate_reason(post_id, message, registry, ig_catalog_keys):
    content_keys = extract_content_keys(message)
    if post_id and post_id in registry["processed_post_ids"]:
        return True, content_keys, "history_post_id"
    registry_match = content_keys & registry["processed_keys"]
    if registry_match:
        return True, content_keys, f"registry:{sorted(registry_match)[0]}"
    ig_match = content_keys & ig_catalog_keys
    if ig_match:
        return True, content_keys, f"instagram:{sorted(ig_match)[0]}"
    return False, content_keys, ""


# ─── Extracción de media del post ────────────────────────────────────────────

def extract_media_list(post):
    items = []
    message = post.get("message", "")
    full_picture = post.get("full_picture")
    attachments = post.get("attachments", {}).get("data", [])

    for att in attachments:
        sub = att.get("subattachments", {}).get("data", [])
        if sub:
            for node in sub:
                media_url = node.get("media", {}).get("source")
                if not media_url:
                    media_url = node.get("media", {}).get("image", {}).get("src")
                m_type = "VIDEO" if "video" in node.get("type", "") else "IMAGE"
                if media_url:
                    items.append({"url": media_url, "type": m_type})
            if items:
                return items, message

    for att in attachments:
        if "video" in att.get("type", ""):
            media_url = att.get("media", {}).get("source")
            if media_url:
                items.append({"url": media_url, "type": "VIDEO"})
                return items, message

    if full_picture:
        items.append({"url": full_picture, "type": "IMAGE"})
        return items, message

    return [], message


# ─── Escaneo por bloques ─────────────────────────────────────────────────────

def _fetch_block(page_id, page_token, page_name, after_cursor=None, block_size=100):
    """
    Descarga un bloque de `block_size` posts del feed de FB comenzando desde `after_cursor`.
    Retorna (posts, next_cursor, api_ok). Posts en orden mas reciente → mas antiguo.
    `api_ok` es False si la API fallo a mitad de bloque (fb_feed es None): en ese
    caso un resultado vacio NO significa fin del feed, solo que hay que reintentar.
    """
    posts = []
    cursor = after_cursor
    api_page_size = 10
    last_cursor = None
    api_ok = True

    for _ in range(block_size // api_page_size):
        fb_feed = get_facebook_page_feed(
            limit=api_page_size,
            after=cursor,
            page_id=page_id,
            page_token=page_token,
        )
        if fb_feed is None:
            api_ok = False
            break
        page_data = fb_feed.get("data") or []
        if not page_data:
            break
        for post in page_data:
            post["_source_page_id"] = page_id
            post["_source_page_name"] = page_name
            post["_source_page_token"] = page_token
        posts.extend(page_data)
        last_cursor = (fb_feed.get("paging") or {}).get("cursors", {}).get("after")
        if not last_cursor:
            break
        cursor = last_cursor

    return posts, last_cursor, api_ok


def _find_newest_uncrossposted(posts, registry, ig_catalog_keys):
    """Retorna el post no publicado mas reciente del bloque que tenga media.

    Devuelve `(post, keys, stats)`. `stats` resume duplicados y posts sin media
    para que el log del bloque explique por que no hubo candidato.
    """
    stats = {"duplicates": 0, "no_media": 0, "reasons": Counter()}
    for post in posts:
        post_id = post.get("id")
        message = post.get("message", "")
        duplicate, content_keys, reason = find_duplicate_reason(post_id, message, registry, ig_catalog_keys)
        if duplicate:
            stats["duplicates"] += 1
            if reason:
                stats["reasons"][reason] += 1
            continue

        media_items, _ = extract_media_list(post)
        if media_items:
            return post, content_keys, stats

        # Si no tiene media, lo marcamos como procesado inmediatamente para no
        # volver a evaluarlo (register_processed_post/load_history son del
        # propio modulo; no se auto-importa para evitar ejecutar el modulo dos veces).
        history = load_history()
        register_processed_post(history, registry, post_id, content_keys, remember_keys=False)
        stats["no_media"] += 1
        logging.info("Post %s ignorado en pre-filtro (sin media).", post_id)
    return None, None, stats


def _format_scan_stats(stats):
    parts = []
    if stats.get("duplicates"):
        parts.append(f"{stats['duplicates']} duplicados")
    if stats.get("no_media"):
        parts.append(f"{stats['no_media']} sin media")
    text = ", ".join(parts) if parts else "0 duplicados, 0 sin media"
    reasons = stats.get("reasons") or {}
    top_reasons = ", ".join(
        f"{reason} x{count}" for reason, count in reasons.most_common(3)
    )
    if top_reasons:
        text += f"; motivos: {top_reasons}"
    return text


def parse_created_time(value):
    """Convierte `created_time` de Graph API a datetime con zona horaria.

    Graph devuelve `2026-10-26T19:26:19+0000`; tambien se aceptan `Z`,
    variantes sin zona y objetos `datetime`.
    """
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    text = str(value or "").strip()
    if not text:
        return None

    candidates = [text]
    if text.endswith("Z"):
        candidates.insert(0, text[:-1] + "+00:00")

    parsed = None
    for candidate in candidates:
        try:
            parsed = datetime.fromisoformat(candidate)
            break
        except ValueError:
            parsed = None

    if parsed is None:
        for fmt in (
            "%Y-%m-%dT%H:%M:%S%z",
            "%Y-%m-%dT%H:%M:%S",
            "%Y-%m-%d %H:%M:%S%z",
            "%Y-%m-%d %H:%M:%S",
        ):
            try:
                parsed = datetime.strptime(text, fmt)
                break
            except ValueError:
                parsed = None

    if parsed is None:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


def _pick_newer_candidate(current_post, current_keys, new_post, new_keys):
    """Conserva el candidato con `created_time` mas reciente entre paginas."""
    if current_post is None:
        return new_post, new_keys

    current_dt = parse_created_time(current_post.get("created_time"))
    new_dt = parse_created_time(new_post.get("created_time"))

    if current_dt is None and new_dt is None:
        current_raw = str(current_post.get("created_time") or "")
        new_raw = str(new_post.get("created_time") or "")
        if new_raw > current_raw:
            return new_post, new_keys
        return current_post, current_keys

    if new_dt is None:
        return current_post, current_keys
    if current_dt is None or new_dt > current_dt:
        return new_post, new_keys
    return current_post, current_keys


# ─── Paginacion Profunda (Deep Cursors) ──────────────────────────────────────────

def load_deep_cursors():
    if DEEP_CURSORS_FILE.exists():
        try:
            return json.loads(DEEP_CURSORS_FILE.read_text(encoding="utf-8"))
        except Exception as e:
            logging.error("Error leyendo deep cursors: %s", e)
    return {}

def save_deep_cursors(cursors_dict):
    try:
        DEEP_CURSORS_FILE.write_text(json.dumps(cursors_dict, indent=2), encoding="utf-8")
    except Exception as e:
        logging.error("Error guardando deep cursors: %s", e)


# ─── Ciclo principal ──────────────────────────────────────────────────────────

def process_new_posts(dry_run=False):
    logging.info(
        "--- Vigia v4.0: Bloques de 100 por pagina | Max 5 bloques | Paginacion profunda (Deep Cursor) ---"
    )
    history = load_history()
    registry = load_dedupe_registry()
    registry["processed_post_ids"].update(history)

    # 1. Catálogo IG para deduplicación (cacheado)
    ig_catalog = get_instagram_library_batch(max_pages=150, use_cache=True)
    if ig_catalog is None:
        # No se retorna 0 ("OK") porque el launcher lo interpretaria como exito:
        # se lanza excepcion para que main() registre el error y --once salga
        # con codigo 1.
        raise RuntimeError("No se pudo sincronizar el catalogo de IG. Abortando.")
    ig_catalog_keys = build_catalog_key_index(ig_catalog)
    logging.info("Catalogo IG: %s captions, %s claves.", len(ig_catalog), len(ig_catalog_keys))

    MAX_BLOCKS = 5    # Bloques de 100 por pagina antes de caer al reporte
    BLOCK_SIZE = 100  # Posts por bloque

    # Guardar el último cursor de los bloques frescos de cada página
    # para usarlo como punto de partida histórico si no hay deep cursor previo
    page_last_cursors = {}

    # Inicializar candidatos ANTES de recorrer las páginas.
    # El refactor de Deep Cursor (a0bd37d) se quitó esta inicialización y
    # dejó al Vigía sin publicar nada: el primer post sin cruzar lanza
    # UnboundLocalError en la línea 354, y el camino "sin posts nuevos"
    # falla en la línea 373.
    candidate_post = None
    candidate_keys = None

    for page_id, page_token, page_name in FB_PAGES:
        if not page_id or not page_token:
            logging.warning("[%s] Sin credenciales - saltando.", page_name)
            continue

        block_cursor = None
        for block_num in range(1, MAX_BLOCKS + 1):
            logging.info(
                "[%s] Bloque %s/%s (%s posts desde %s)...",
                page_name, block_num, MAX_BLOCKS, BLOCK_SIZE,
                "inicio" if block_cursor is None else "cursor"
            )
            block_posts, next_cursor, api_ok = _fetch_block(
                page_id, page_token, page_name,
                after_cursor=block_cursor,
                block_size=BLOCK_SIZE,
            )
            if not block_posts:
                if api_ok:
                    logging.info("[%s] Bloque %s vacio. No hay mas posts en esta pagina.", page_name, block_num)
                else:
                    # Bloque vacio por FALLO de API, no por fin de pagina:
                    # se rompe sin asumir nada y se reintenta en el proximo ciclo.
                    logging.warning(
                        "[%s] Bloque %s: la API fallo (sin datos). Se reintentara en el proximo ciclo.",
                        page_name, block_num,
                    )
                break

            new_post, new_keys, scan_stats = _find_newest_uncrossposted(
                block_posts, registry, ig_catalog_keys
            )
            if new_post:
                logging.info("[%s] Bloque %s: post nuevo encontrado: %s", page_name, block_num, new_post.get("id"))
                # Elegir el candidato mas reciente entre todas las paginas.
                candidate_post, candidate_keys = _pick_newer_candidate(
                    candidate_post, candidate_keys, new_post, new_keys
                )
                break  # Un candidato por página; seguir con la siguiente

            logging.info(
                "[%s] Bloque %s: sin candidatos en %s posts (%s). Siguiente bloque.",
                page_name, block_num, len(block_posts), _format_scan_stats(scan_stats)
            )
            block_cursor = next_cursor
            if not block_cursor:
                logging.info("[%s] Sin mas posts en la pagina.", page_name)
                break
                
        # Guardamos donde quedó el feed fresco para esta página
        if block_cursor:
            page_last_cursors[page_id] = block_cursor

    # 3. Fallback a Paginación Profunda (Deep Cursor) si ningún bloque fresco tenía contenido
    if candidate_post is None:
        logging.info(
            "Ninguno de los bloques frescos tenia posts nuevos. Iniciando recuperación historica profunda (Deep Cursor)..."
        )
        deep_cursors = load_deep_cursors()
        
        MAX_DEEP_BLOCKS = 3  # Bloques a avanzar por ciclo buscando un post perdido
        
        for page_id, page_token, page_name in FB_PAGES:
            if not page_id or not page_token:
                continue
                
            cursor = deep_cursors.get(page_id)
            if cursor == "DONE":
                logging.info("[%s] Pagina ya recorrida al fondo (DONE). Saltando.", page_name)
                continue
            if not cursor:
                cursor = page_last_cursors.get(page_id)
                if not cursor:
                    continue  # La página tiene menos de MAX_BLOCKS en total, no hay historial profundo

            logging.info("[%s] Retomando historial profundo desde cursor.", page_name)
            
            for deep_block_num in range(1, MAX_DEEP_BLOCKS + 1):
                block_posts, next_cursor, api_ok = _fetch_block(
                    page_id, page_token, page_name,
                    after_cursor=cursor,
                    block_size=BLOCK_SIZE,
                )
                if not block_posts:
                    if api_ok:
                        logging.info("[%s] Historial profundo agotado (fin de la pagina).", page_name)
                        # Marcamos la pagina como DONE para que los proximos ciclos
                        # no re-escaneen los mismos bloques de siempre (ahorra API).
                        deep_cursors[page_id] = "DONE"
                        save_deep_cursors(deep_cursors)
                    else:
                        # Bloque vacio por FALLO de API, no por fin de pagina:
                        # NO se marca DONE (perderia el backlog) ni se mueve el
                        # cursor; el proximo ciclo reintenta desde el mismo punto.
                        logging.warning(
                            "[%s] Bloque historico %s: la API fallo (sin datos). "
                            "Se conserva el cursor para reintentar.",
                            page_name, deep_block_num,
                        )
                    break
                    
                new_post, new_keys, scan_stats = _find_newest_uncrossposted(
                    block_posts, registry, ig_catalog_keys
                )
                if new_post:
                    logging.info("[%s] Rescate profundo exitoso: %s", page_name, new_post.get("id"))
                    # Comparar con candidatos de las otras paginas: el rescate
                    # profundo no debe quedarse con el primero que aparezca.
                    candidate_post, candidate_keys = _pick_newer_candidate(
                        candidate_post, candidate_keys, new_post, new_keys
                    )
                    # NO actualizamos el cursor, para que en el prox ciclo siga revisando este mismo bloque
                    break 
                
                # El bloque profundo entero ya estaba cruzado. Avanzamos el cursor para hundirnos más en la historia
                cursor = next_cursor
                if cursor is None:
                    # Sin cursor siguiente el feed llego al fondo (D47):
                    # guardar None haria que el proximo ciclo volviera a
                    # page_last_cursors y re-escaneara los mismos bloques.
                    deep_cursors[page_id] = "DONE"
                else:
                    deep_cursors[page_id] = cursor
                save_deep_cursors(deep_cursors)
                
                logging.info(
                    "[%s] Bloque historico %s sin candidatos (%s). Cursor hundido al siguiente nivel.",
                    page_name, deep_block_num, _format_scan_stats(scan_stats)
                )
                
                if not cursor:
                    break
                
        if candidate_post is None:
            logging.info("No hay contenido pendiente ni en bloques frescos ni en la historia profunda visible este ciclo. Todo al dia.")
            return CYCLE_NO_CANDIDATE

    logging.info(
        "Candidato mas reciente entre paginas: %s (%s, %s).",
        candidate_post.get("id"),
        candidate_post.get("_source_page_name", "desconocida"),
        candidate_post.get("created_time", "sin fecha"),
    )

    # 4. Subir el candidato encontrado
    post_id = candidate_post.get("id")
    message = candidate_post.get("message", "")
    src_page = candidate_post.get("_source_page_name", "desconocida")

    if dry_run:
        logging.info("[%s] Dry-Run: subiria post %s", src_page, post_id)
        return CYCLE_PUBLISHED

    logging.info("[%s] Procesando publicacion de: %s", src_page, post_id)
    media_items, original_caption = extract_media_list(candidate_post)

    if not media_items:
        logging.info("[%s] Post %s sin media. Descartando.", src_page, post_id)
        register_processed_post(history, registry, post_id, candidate_keys, remember_keys=False)
        return CYCLE_NO_CANDIDATE

    final_caption = (original_caption or "").strip() + CAPTION_SIGNATURE
    at_least_one_success = False
    temp_file = None
    local_path = None

    for idx, item in enumerate(media_items):
        targets = ["REELS"] if item["type"] == "VIDEO" else ["FEED"]

        import requests

        try:
            logging.info("[%s] Descargando media para optimizacion local...", src_page)
            temp_file = BASE_DIR / f"temp_vigia_{post_id}_{idx}.mp4"
            resp = requests.get(item["url"], stream=True, timeout=30)
            with open(temp_file, "wb") as f:
                for chunk in resp.iter_content(chunk_size=8192):
                    f.write(chunk)

            local_path = ensure_ig_compatibility(str(temp_file), force_recode=True)
            vinfo = probe_video(local_path)
            duration = vinfo.get("duration_seconds", 0)

            active_targets = list(targets)
            # NOTA: El fallback FEED fue eliminado — usaba _create_ig_video_container("REELS", share_to_feed=True)
            # que es idéntico al target REELS base y causaba 24 rechazos binarios dobles sin beneficio.
            # Videos >90s son recortados a 90s por ensure_ig_compatibility en el target REELS.
        except Exception as e:
            logging.error("[%s] Fallo descarga/optimizacion local: %s", src_page, e)
            continue

        for target_type in active_targets:
            if not check_ig_publish_limit():
                logging.error("[%s] Limite oficial de Instagram alcanzado. Abortando.", src_page)
                break

            logging.info("[%s] Subiendo item %s/%s a IG %s (Binario)...", src_page, idx + 1, len(media_items), target_type)
            path_for_target = local_path

            if target_type == "STORIES" and item["type"] == "VIDEO":
                path_for_target = ensure_ig_compatibility(local_path, max_duration=60)
            elif target_type == "REELS" and duration > 90:
                path_for_target = ensure_ig_compatibility(local_path, max_duration=90)

            from meta_uploader import (
                _create_ig_video_container,
                upload_ig_binary,
                publish_ig_container,
            )

            creation_id = None
            if item["type"] == "VIDEO":
                if target_type in ("REELS", "FEED"):
                    creation_id = _create_ig_video_container("REELS", caption=final_caption, share_to_feed=True)
                elif target_type == "STORIES":
                    creation_id = _create_ig_video_container("STORIES")

                if creation_id:
                    logging.info("[%s] Contenedor %s creado. Esperando que Meta lo active para upload...", src_page, target_type)
                    if not wait_for_ig_container_upload_ready(creation_id):
                        logging.error("[%s] Contenedor %s nunca llegó a UPLOAD_IN_PROGRESS. Abortando subida.", src_page, target_type)
                    else:
                        # Probe del clip — diagnóstico para entender ProcessingFailedError
                        # (probe_video ya importado a nivel de módulo en línea 11)
                        _p = probe_video(path_for_target)
                        _fps = _p.get("avg_frame_rate", "?")
                        try:
                            _n, _d = _fps.split("/")
                            _fps = f"{round(int(_n)/int(_d),2)}fps" if int(_d) else _fps
                        except Exception:
                            pass
                        logging.info(
                            "[CLIP-SPECS] %s | %dx%d | %.1fs | %.2f MB | %.2f Mbps | %s | codec:%s pix:%s",
                            Path(path_for_target).name,
                            _p.get("width", 0), _p.get("height", 0),
                            _p.get("duration_seconds", 0),
                            _p.get("size_bytes", 0) / 1_048_576,
                            _p.get("bit_rate", 0) / 1_000_000,
                            _fps,
                            _p.get("codec_name", "?"),
                            _p.get("pix_fmt", "?"),
                        )
                        if upload_ig_binary(creation_id, path_for_target):
                            if wait_for_ig_container(creation_id):
                                ig_id = publish_ig_container(creation_id)
                                if ig_id:
                                    logging.info("[%s] Video %s publicado en IG %s", src_page, post_id, target_type)
                                    at_least_one_success = True

                if path_for_target != local_path and os.path.exists(path_for_target):
                    try:
                        os.remove(path_for_target)
                    except Exception:
                        pass

            else:
                from meta_uploader import create_ig_media_container_from_url
                creation_id = create_ig_media_container_from_url(
                    item["url"], "IMAGE", final_caption, target=target_type
                )
                if creation_id and wait_for_ig_container(creation_id):
                    ig_id = publish_ig_container(creation_id)
                    if ig_id:
                        logging.info("[%s] Imagen %s publicada en IG %s", src_page, post_id, target_type)
                        at_least_one_success = True

        if local_path and os.path.exists(local_path):
            try:
                os.remove(local_path)
            except Exception:
                pass
        if temp_file and local_path != str(temp_file) and os.path.exists(str(temp_file)):
            try:
                os.remove(str(temp_file))
            except Exception:
                pass

    if at_least_one_success:
        register_processed_post(history, registry, post_id, candidate_keys, remember_keys=True)
        ig_catalog_keys.update(candidate_keys or set())
        # Reset conteo de fallos al publicar con éxito
        failure_counts = load_failure_counts()
        failure_counts.pop(post_id, None)
        save_failure_counts(failure_counts)
        logging.info("Post %s publicado y registrado. Bash hara pausa de 720s.", post_id)
        # Limpieza de temporales huérfanos en .ig_temp
        ig_temp_dir = BASE_DIR / ".ig_temp"
        if ig_temp_dir.exists():
            removed = 0
            freed_mb = 0.0
            for tmp in ig_temp_dir.iterdir():
                if tmp.is_file():
                    try:
                        freed_mb += tmp.stat().st_size / (1024 * 1024)
                        tmp.unlink()
                        removed += 1
                    except Exception:
                        pass
            if removed:
                logging.info("[LIMPIEZA] Eliminados %s temporales huérfanos en .ig_temp (%.1f MB liberados).", removed, freed_mb)
        return CYCLE_PUBLISHED

    # Post falló en todos los targets — incrementar contador de fallos
    failure_counts = load_failure_counts()
    failure_counts[post_id] = failure_counts.get(post_id, 0) + 1
    save_failure_counts(failure_counts)

    if failure_counts[post_id] >= MAX_CONSECUTIVE_FAILURES:
        logging.warning(
            "[SKIP] Post %s falló %s veces consecutivas. Marcando como procesado para no reintentar infinitamente.",
            post_id, failure_counts[post_id],
        )
        register_processed_post(history, registry, post_id, candidate_keys, remember_keys=False)
        failure_counts.pop(post_id, None)
        save_failure_counts(failure_counts)
    else:
        logging.warning(
            "[FALLO] Post %s: intento %s/%s fallido. Se reintentara en el proximo ciclo.",
            post_id, failure_counts[post_id], MAX_CONSECUTIVE_FAILURES,
        )

    logging.info("Ciclo finalizado sin publicacion confirmada.")
    return CYCLE_PUBLISH_FAILED


def main():
    parser = argparse.ArgumentParser(
        description="Agente Vigia 4.0: Bloques por pagina + paginacion profunda (Deep Cursor)"
    )
    parser.add_argument("--dry-run", action="store_true", help="Solo muestra lo que subiria.")
    parser.add_argument("--once", action="store_true", help="Ejecuta una vez y sale.")
    args = parser.parse_args()

    while True:
        try:
            cycle_result = process_new_posts(dry_run=args.dry_run)
        except Exception as e:
            logging.error("Error en pulso del Vigia: %s", e)
            if args.once or args.dry_run:
                # No escondemos el fallo como "OK" (código 0): el launcher
                # interpreta 0 como crosspost exitoso. Con --once salimos
                # con código 1 para que el widget muestre el error real.
                sys.exit(1)
            cycle_result = None

        if args.once:
            # 0 = se publico algo, 2 = sin candidatos (duplicados/sin media),
            # 3 = candidato encontrado pero fallo la publicacion, 1 = error.
            if cycle_result == CYCLE_PUBLISHED:
                sys.exit(0)
            if cycle_result == CYCLE_NO_CANDIDATE:
                sys.exit(2)
            sys.exit(3)
        if args.dry_run:
            break

        if cycle_result == CYCLE_PUBLISHED:
            wait_time = 600
            logging.info("Backlog pendiente. Reintentando en 10 minutos...")
        elif cycle_result == CYCLE_PUBLISH_FAILED:
            wait_time = 600
            logging.info("Fallo de publicacion. Reintentando en 10 minutos...")
        elif cycle_result == CYCLE_NO_CANDIDATE:
            wait_time = 86400
            logging.info("Todo al dia. Durmiendo 24 horas...")
        else:
            wait_time = 600
            logging.info("Error de ciclo. Reintentando en 10 minutos...")

        time.sleep(wait_time)


if __name__ == "__main__":
    main()
