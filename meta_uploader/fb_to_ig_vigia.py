import json
import logging
import time
import argparse
import os
import re
import unicodedata
from pathlib import Path

from meta_uploader import (
    FB_PAGE_ID,
    META_FB_PAGE_TOKEN,
    IG_USER_ID,
    get_facebook_page_feed,
    get_instagram_library_batch,
    wait_for_ig_container,
    publish_ig_container,
    check_ig_publish_limit,
    ensure_ig_compatibility,
    probe_video,
)

BASE_DIR = Path(__file__).resolve().parent
HISTORY_FILE = BASE_DIR / "crosspost_history.json"
DEDUPE_REGISTRY_FILE = BASE_DIR / "crosspost_dedupe_registry.json"
CAPTION_SIGNATURE = "\n\n#PW\nSíguenos también en Facebook"
STEM_PATTERNS = (
    re.compile(r"\b\d{8}[\s_-]\d{6}(?:_\d+)?\b", re.IGNORECASE),
    re.compile(r"\b\d{8}[-_]\d{4}\b", re.IGNORECASE),
    re.compile(r"\bvid-\d{8}-wa\d+\b", re.IGNORECASE),
)
PW_PREFIX_RE = re.compile(r"^\s*pw\s*\|\s*\d{4}-\d{2}-\d{2}\s*\|\s*", re.IGNORECASE)
NOISE_TOKEN_RE = re.compile(r"(?i)\s*#(?:pw|full|teaser|hq|pc|p)\b")
MULTISPACE_RE = re.compile(r"\s+")

# Páginas de Facebook → Instagram
# Cada entrada: (page_id, page_token, page_name)
FB_PAGES = [
    (
        os.environ.get("META_FB_PAGE_ID", FB_PAGE_ID),
        os.environ.get("META_FB_PAGE_TOKEN", META_FB_PAGE_TOKEN),
        "Performatic Writings Cali",
    ),
    (
        os.environ.get("META_FB_PAGE_ID_TEASER", "1347014641828725"),
        os.environ.get(
            "META_FB_PAGE_TOKEN_TEASER",
            "EAAUr7rtgpvMBSmuoJG2DaiWjd8G6pjRDVOdBUyLtDZBupMeEJd9Ef8RuZAqi1Yhpb6CZBWYjpOwEz3Ht6SB9FkZC3SDDnSa7rLtNTTMVlCjMAZAA4di3m7M2IFeFDHfOqog3eUqL7h0alxQ8DIvc8v9mf84m4ytfYQEWl1C3Vg6LjKKR1NbcJYXnGkbje2D0GWcvZCoDJZC",
        ),
        "Shirabyoshi Writings",
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
        return {"processed_post_ids": set(), "processed_keys": set(data)}
    if not isinstance(data, dict):
        return {"processed_post_ids": set(), "processed_keys": set()}
    return {
        "processed_post_ids": set(data.get("processed_post_ids") or []),
        "processed_keys": set(data.get("processed_keys") or []),
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


def _normalize_marker(value):
    raw = _strip_accents(value or "")
    raw = raw.replace(CAPTION_SIGNATURE, "")
    lines = [line.strip() for line in raw.splitlines() if line.strip()]
    text = lines[0] if lines else ""
    text = PW_PREFIX_RE.sub("", text)
    text = NOISE_TOKEN_RE.sub("", text)
    text = MULTISPACE_RE.sub(" ", text).strip(" |-_").lower()
    return text


def _normalize_stem(value):
    stem = _strip_accents(value or "").strip().lower()
    stem = re.sub(r"[\s-]+", "_", stem)
    return stem


def extract_content_keys(text):
    raw = str(text or "")
    keys = set()
    marker = _normalize_marker(raw)
    if marker:
        keys.add(f"text:{marker}")
    normalized_raw = _strip_accents(raw)
    for pattern in STEM_PATTERNS:
        for match in pattern.findall(normalized_raw):
            keys.add(f"stem:{_normalize_stem(match)}")
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
    Retorna (posts, next_cursor). Posts en orden mas reciente → mas antiguo.
    """
    posts = []
    cursor = after_cursor
    api_page_size = 10
    last_cursor = None

    for _ in range(block_size // api_page_size):
        fb_feed = get_facebook_page_feed(
            limit=api_page_size,
            after=cursor,
            page_id=page_id,
            page_token=page_token,
        )
        if fb_feed is None:
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

    return posts, last_cursor


def _find_newest_uncrossposted(posts, registry, ig_catalog_keys):
    """Retorna el primer post no publicado (el mas reciente) de un bloque que tenga media, o (None, None)."""
    for post in posts:
        post_id = post.get("id")
        message = post.get("message", "")
        duplicate, content_keys, _ = find_duplicate_reason(post_id, message, registry, ig_catalog_keys)
        if not duplicate:
            media_items, _ = extract_media_list(post)
            if media_items:
                return post, content_keys
            else:
                # Si no tiene media, lo marcamos como procesado inmediatamente para no volver a evaluarlo
                from fb_to_ig_vigia import register_processed_post, HISTORY_FILE, load_history
                history = load_history()
                register_processed_post(history, registry, post_id, content_keys, remember_keys=False)
                logging.info("Post %s ignorado en pre-filtro (sin media).", post_id)
    return None, None


# ─── Fallback al reporte histórico ───────────────────────────────────────────

def _pick_from_report(registry, ig_catalog_keys):
    """
    Lee missing_crossposts_report.json y devuelve el entry más reciente
    que aún no haya sido publicado en IG, como (entry_dict, content_keys).
    """
    report_file = BASE_DIR / "missing_crossposts_report.json"
    if not report_file.exists():
        logging.info("No existe reporte historico. Nada que hacer.")
        return None, None
    try:
        with open(report_file, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception as e:
        logging.error("Error al leer reporte historico: %s", e)
        return None, None
    missing = data.get("missing_posts") or []
    if not missing:
        logging.info("Reporte historico vacio. Todo sincronizado.")
        return None, None
    # El reporte viene ordenado del mas reciente al mas antiguo (por audit_crosspost.py)
    for entry in missing:
        post_id = entry.get("post_id")
        message = entry.get("caption", "")
        duplicate, content_keys, _ = find_duplicate_reason(post_id, message, registry, ig_catalog_keys)
        if not duplicate:
            logging.info("Reporte historico: candidato sin publicar: %s (%s)", post_id, entry.get("page"))
            return entry, content_keys
    logging.info("Reporte historico: todos los entries ya publicados.")
    return None, None


def _resolve_full_post_from_report_entry(entry):
    """
    El reporte guarda solo metadatos. Llama a la API de FB para obtener
    el post completo con attachments y retorna el dict enriquecido.
    """
    import requests as req_lib
    post_id = entry.get("post_id")
    src_page = entry.get("page", "")
    if "Shirabyoshi" in src_page:
        token = os.environ.get(
            "META_FB_PAGE_TOKEN_TEASER",
            "EAAUr7rtgpvMBSmuoJG2DaiWjd8G6pjRDVOdBUyLtDZBupMeEJd9Ef8RuZAqi1Yhpb6CZBWYjpOwEz3Ht6SB9FkZC3SDDnSa7rLtNTTMVlCjMAZAA4di3m7M2IFeFDHfOqog3eUqL7h0alxQ8DIvc8v9mf84m4ytfYQEWl1C3Vg6LjKKR1NbcJYXnGkbje2D0GWcvZCoDJZC",
        )
    else:
        token = os.environ.get("META_FB_PAGE_TOKEN", META_FB_PAGE_TOKEN)
    url = (
        f"https://graph.facebook.com/v21.0/{post_id}"
        f"?fields=message,full_picture,attachments{{media,subattachments,type}}"
        f"&access_token={token}"
    )
    try:
        resp = req_lib.get(url, timeout=30)
        if resp.status_code == 200:
            full = resp.json()
            full["_source_page_name"] = src_page
            return full
    except Exception as e:
        logging.error("Error al resolver post %s desde API: %s", post_id, e)
    return None


# ─── Ciclo principal ──────────────────────────────────────────────────────────

def process_new_posts(dry_run=False):
    logging.info(
        "--- Vigia v4.0: Bloques de 100 por pagina | Max 5 bloques | Fallback reporte historico ---"
    )
    history = load_history()
    registry = load_dedupe_registry()
    registry["processed_post_ids"].update(history)

    # 1. Catálogo IG para deduplicación (cacheado)
    ig_catalog = get_instagram_library_batch(max_pages=150, use_cache=True)
    if ig_catalog is None:
        logging.error("Fallo critico: No se pudo sincronizar el catalogo de IG. Abortando.")
        return 0
    ig_catalog_keys = build_catalog_key_index(ig_catalog)
    logging.info("Catalogo IG: %s captions, %s claves.", len(ig_catalog), len(ig_catalog_keys))

    MAX_BLOCKS = 5    # Bloques de 100 por pagina antes de caer al reporte
    BLOCK_SIZE = 100  # Posts por bloque

    # 2. Búsqueda por bloques en cada página de FB
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
            block_posts, next_cursor = _fetch_block(
                page_id, page_token, page_name,
                after_cursor=block_cursor,
                block_size=BLOCK_SIZE,
            )
            if not block_posts:
                logging.info("[%s] Bloque %s vacio. No hay mas posts en esta pagina.", page_name, block_num)
                break

            new_post, new_keys = _find_newest_uncrossposted(block_posts, registry, ig_catalog_keys)
            if new_post:
                logging.info("[%s] Bloque %s: post nuevo encontrado: %s", page_name, block_num, new_post.get("id"))
                # Elegir el candidato más reciente entre todas las páginas
                if candidate_post is None or new_post.get("created_time", "") > candidate_post.get("created_time", ""):
                    candidate_post = new_post
                    candidate_keys = new_keys
                break  # Un candidato por página; seguir con la siguiente

            logging.info(
                "[%s] Bloque %s: los %s posts ya estaban publicados. Siguiente bloque.",
                page_name, block_num, len(block_posts)
            )
            block_cursor = next_cursor
            if not block_cursor:
                logging.info("[%s] Sin mas posts en la pagina.", page_name)
                break

    # 3. Fallback al reporte histórico si ningún bloque fresco tenía contenido nuevo
    if candidate_post is None:
        logging.info(
            "Ninguno de los %s bloques de ninguna pagina tenia posts nuevos. Consultando reporte historico...",
            MAX_BLOCKS,
        )
        report_entry, candidate_keys = _pick_from_report(registry, ig_catalog_keys)
        if report_entry is not None:
            candidate_post = _resolve_full_post_from_report_entry(report_entry)
            if candidate_post is None:
                logging.error("No se pudo resolver el post del reporte via API. Abortando.")
                return 0
        else:
            logging.info("No hay contenido pendiente en bloques frescos ni en el reporte. Todo al dia.")
            return 0

    # 4. Subir el candidato encontrado
    post_id = candidate_post.get("id")
    message = candidate_post.get("message", "")
    src_page = candidate_post.get("_source_page_name", "desconocida")

    if dry_run:
        logging.info("[%s] Dry-Run: subiria post %s", src_page, post_id)
        return 1

    logging.info("[%s] Procesando publicacion de: %s", src_page, post_id)
    media_items, original_caption = extract_media_list(candidate_post)

    if not media_items:
        logging.info("[%s] Post %s sin media. Descartando.", src_page, post_id)
        register_processed_post(history, registry, post_id, candidate_keys, remember_keys=False)
        return 0

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
            if duration > 90 and "FEED" not in active_targets:
                logging.info("[%s] Video largo (%.2fs): activando Feed Completo.", src_page, duration)
                active_targets.append("FEED")
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
                    logging.info("[%s] Contenedor %s listo. Esperando propagacion...", src_page, target_type)
                    time.sleep(2)
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
        logging.info("Post %s publicado y registrado. Bash hara pausa de 720s.", post_id)
        return 1

    logging.info("Ciclo finalizado sin publicaciones nuevas.")
    return 0


def main():
    parser = argparse.ArgumentParser(
        description="Agente Vigia 4.0: Bloques por pagina + fallback reporte historico"
    )
    parser.add_argument("--dry-run", action="store_true", help="Solo muestra lo que subiria.")
    parser.add_argument("--once", action="store_true", help="Ejecuta una vez y sale.")
    args = parser.parse_args()

    while True:
        try:
            rescued = process_new_posts(dry_run=args.dry_run)
        except Exception as e:
            logging.error("Error en pulso del Vigia: %s", e)
            rescued = 0

        if args.once or args.dry_run:
            break

        if rescued > 0:
            wait_time = 600
            logging.info("Backlog pendiente. Reintentando en 10 minutos...")
        else:
            wait_time = 86400
            logging.info("Todo al dia. Durmiendo 24 horas...")

        time.sleep(wait_time)


if __name__ == "__main__":
    main()
