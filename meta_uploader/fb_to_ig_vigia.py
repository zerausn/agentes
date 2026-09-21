import json
import logging
import time
import argparse
import os
import re
import unicodedata
from pathlib import Path

# Importamos motores del uploader base
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
POLL_INTERVAL_SECONDS = 86400  # 24 horas (Daily)
CAPTION_SIGNATURE = "\n\n#PW\nSíguenos también en Facebook"
STEM_PATTERNS = (
    re.compile(r"\b\d{8}[\s_-]\d{6}(?:_\d+)?\b", re.IGNORECASE),
    re.compile(r"\b\d{8}[-_]\d{4}\b", re.IGNORECASE),
    re.compile(r"\bvid-\d{8}-wa\d+\b", re.IGNORECASE),
)
PW_PREFIX_RE = re.compile(r"^\s*pw\s*\|\s*\d{4}-\d{2}-\d{2}\s*\|\s*", re.IGNORECASE)
NOISE_TOKEN_RE = re.compile(r"(?i)\s*#(?:pw|full|teaser|hq|pc|p)\b")
MULTISPACE_RE = re.compile(r"\s+")

# ----------------------------------------------------------------
# Páginas de Facebook a monitorear → Instagram
# Se leen desde el entorno para soportar múltiples páginas sin
# modificar el módulo base (meta_uploader.py).
# Cada entrada: (page_id, page_token, page_name)
# ----------------------------------------------------------------
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
            # Fallback hardcoded: proot puede limpiar el entorno en Android
            "EAAUr7rtgpvMBSmuoJG2DaiWjd8G6pjRDVOdBUyLtDZBupMeEJd9Ef8RuZAqi1Yhpb6CZBWYjpOwEz3Ht6SB9FkZC3SDDnSa7rLtNTTMVlCjMAZAA4di3m7M2IFeFDHfOqog3eUqL7h0alxQ8DIvc8v9mf84m4ytfYQEWl1C3Vg6LjKKR1NbcJYXnGkbje2D0GWcvZCoDJZC",
        ),
        "Shirabyoshi Writings",
    ),
]

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - [VIGIA-3.0] - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler(BASE_DIR / "fb_to_ig_vigia.log", encoding="utf-8"),
        logging.StreamHandler(),
    ],
)


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


def register_processed_post(history, registry, post_id, content_keys=None, remember_keys=True):
    if post_id:
        history.add(post_id)
        registry["processed_post_ids"].add(post_id)
        save_history(history)

    if remember_keys and content_keys:
        registry["processed_keys"].update(content_keys)

    save_dedupe_registry(registry)


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


def extract_media_list(post):
    """
    Extrae CUALQUIER media del post.
    Si es un carrusel devuelve items individuales.
    """
    items = []
    message = post.get("message", "")
    full_picture = post.get("full_picture")
    attachments = post.get("attachments", {}).get("data", [])

    # Caso 1: sub-attachments (Album/Carrusel)
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

    # Caso 2: Video individual
    for att in attachments:
        if "video" in att.get("type", ""):
            media_url = att.get("media", {}).get("source")
            if media_url:
                items.append({"url": media_url, "type": "VIDEO"})
                return items, message

    # Caso 3: Foto individual simple
    if full_picture:
        items.append({"url": full_picture, "type": "IMAGE"})
        return items, message

    return [], message


def _fetch_all_posts_from_page(page_id, page_token, page_name, known_post_ids=None, limit_per_page=5, max_pages=20):
    """
    Recorre paginas del feed de una pagina de Facebook (hasta max_pages o hit de historial).
    Retorna lista de posts enriquecidos con '_source_page_*' para debug.
    """
    posts = []
    after_cursor = None
    page_num = 0

    while True:
        page_num += 1
        logging.info(
            "[%s] Solicitando pagina %s de feed FB (after=%s)...",
            page_name, page_num, after_cursor,
        )
        fb_feed = get_facebook_page_feed(
            limit=limit_per_page,
            after=after_cursor,
            page_id=page_id,
            page_token=page_token,
        )

        if fb_feed is None:
            logging.error(
                "[%s] Fallo al obtener feed. Abortando paginacion de esta pagina.", page_name
            )
            break

        page_data = fb_feed.get("data") or []
        if not page_data:
            logging.info("[%s] No hay mas posts en el feed.", page_name)
            break

        boundary_reached = False
        consecutive_known = 0

        for post in page_data:
            post["_source_page_id"] = page_id
            post["_source_page_name"] = page_name
            post["_source_page_token"] = page_token

            post_id_val = post.get("id")
            if known_post_ids and post_id_val in known_post_ids:
                consecutive_known += 1
                if consecutive_known >= 3:
                    boundary_reached = True
            else:
                consecutive_known = 0

        posts.extend(page_data)

        if boundary_reached:
            logging.info("[%s] Boundary historico alcanzado (3 posts conocidos consecutivos). Deteniendo escaneo temprano.", page_name)
            break

        if page_num >= max_pages:
            logging.info("[%s] Limite de %s paginas alcanzado. Deteniendo escaneo.", page_name, max_pages)
            break

        after_cursor = (fb_feed.get("paging") or {}).get("cursors", {}).get("after")
        if not after_cursor:
            break

    return posts


def process_new_posts(dry_run=False):
    logging.info(
        "--- Iniciando ciclo de reconciliacion FB -> IG "
        "(Multi-Pagina, Mas Reciente Primero) ---"
    )
    history = load_history()
    registry = load_dedupe_registry()
    registry["processed_post_ids"].update(history)

    # 1. Catalogo IG para deduplicacion
    ig_catalog = get_instagram_library_batch(max_pages=150, use_cache=True)
    if ig_catalog is None:
        logging.error(
            "Fallo critico: No se pudo sincronizar el catalogo de Instagram. Abortando."
        )
        return 0
    ig_catalog_keys = build_catalog_key_index(ig_catalog)
    logging.info(
        "Catalogo IG cargado: %s captions remotos, %s claves canonicas.",
        len(ig_catalog),
        len(ig_catalog_keys),
    )

    # 2. Recopilar posts de TODAS las paginas configuradas
    all_posts = []
    for page_id, page_token, page_name in FB_PAGES:
        if not page_id or not page_token:
            logging.warning("[%s] Sin credenciales — saltando pagina.", page_name)
            continue
        logging.info("[%s] Recopilando feed (page_id=%s)...", page_name, page_id)
        page_posts = _fetch_all_posts_from_page(
            page_id, page_token, page_name, known_post_ids=registry["processed_post_ids"]
        )
        logging.info("[%s] %s posts obtenidos.", page_name, len(page_posts))
        all_posts.extend(page_posts)

    if not all_posts:
        logging.info("No hay posts en ninguna pagina. Nada que procesar.")
        return 0

    # 3. Ordenar de MAS RECIENTE a MENOS RECIENTE
    all_posts.sort(key=lambda p: p.get("created_time", ""), reverse=True)
    logging.info(
        "Total posts combinados a revisar (ordenados mas reciente primero): %s",
        len(all_posts),
    )

    # 4. Procesar
    new_count = 0
    backlog_scan_active = True

    for post in all_posts:
        if not backlog_scan_active:
            break

        post_id = post.get("id")
        message = post.get("message", "")
        src_page = post.get("_source_page_name", "desconocida")

        duplicate, content_keys, duplicate_reason = find_duplicate_reason(
            post_id, message, registry, ig_catalog_keys
        )

        if duplicate:
            logging.info(
                "[%s] Post %s omitido por duplicado (%s).",
                src_page, post_id, duplicate_reason,
            )
            register_processed_post(history, registry, post_id, content_keys, remember_keys=True)
            continue

        if dry_run:
            logging.info(
                "[%s] Dry-Run: Post %s detectado como faltante. Claves=%s",
                src_page, post_id, sorted(content_keys),
            )
            new_count += 1
            continue

        logging.info("[%s] Procesando rescate de post: %s", src_page, post_id)
        media_items, original_caption = extract_media_list(post)

        if not media_items:
            logging.info("[%s] Post %s no tiene media. Saltando.", src_page, post_id)
            register_processed_post(history, registry, post_id, remember_keys=False)
            continue

        final_caption = (original_caption or "").strip() + CAPTION_SIGNATURE

        at_least_one_success = False
        temp_file = None
        local_path = None

        for idx, item in enumerate(media_items):
            targets = ["REELS"] if item["type"] == "VIDEO" else ["FEED"]

            from meta_uploader import ensure_ig_compatibility
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
                    logging.info(
                        "[%s] Video largo (%.2fs): activando Feed Completo.",
                        src_page, duration,
                    )
                    active_targets.append("FEED")
            except Exception as e:
                logging.error("[%s] Fallo descarga/optimizacion local: %s", src_page, e)
                continue

            for target_type in active_targets:
                if not check_ig_publish_limit():
                    logging.error(
                        "[%s] Limite oficial de Instagram alcanzado. Abortando ciclo.",
                        src_page,
                    )
                    backlog_scan_active = False
                    break

                logging.info(
                    "[%s] Subiendo item %s/%s a IG %s (Binario)...",
                    src_page, idx + 1, len(media_items), target_type,
                )
                path_for_target = local_path

                if target_type == "STORIES" and item["type"] == "VIDEO":
                    path_for_target = ensure_ig_compatibility(local_path, max_duration=60)
                elif target_type == "REELS" and duration > 90:
                    logging.info(
                        "[%s] Recortando Reel a 90s para asegurar aceptacion.", src_page
                    )
                    path_for_target = ensure_ig_compatibility(local_path, max_duration=90)

                from meta_uploader import (
                    _create_ig_video_container,
                    upload_ig_binary,
                    publish_ig_container,
                )

                creation_id = None
                if item["type"] == "VIDEO":
                    if target_type in ("REELS", "FEED"):
                        creation_id = _create_ig_video_container(
                            "REELS", caption=final_caption, share_to_feed=True
                        )
                    elif target_type == "STORIES":
                        creation_id = _create_ig_video_container("STORIES")

                    if creation_id:
                        logging.info(
                            "[%s] Contenedor %s listo. Esperando propagacion...",
                            src_page, target_type,
                        )
                        time.sleep(2)
                        if upload_ig_binary(creation_id, path_for_target):
                            if wait_for_ig_container(creation_id):
                                ig_id = publish_ig_container(creation_id)
                                if ig_id:
                                    logging.info(
                                        "[%s] Video %s publicado en IG %s",
                                        src_page, post_id, target_type,
                                    )
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
                            logging.info(
                                "[%s] Imagen %s publicada en IG %s",
                                src_page, post_id, target_type,
                            )
                            at_least_one_success = True

            if not backlog_scan_active:
                break

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
            register_processed_post(history, registry, post_id, content_keys, remember_keys=True)
            ig_catalog_keys.update(content_keys)
            new_count += 1

        if new_count > 50:
            logging.warning("Lote grande alcanzado (50+). Pausando para goteo adaptativo.")
            break

    logging.info("Ciclo finalizado. Rescatados %s posts en total.", new_count)
    return new_count


def main():
    parser = argparse.ArgumentParser(
        description=(
            "Agente Vigia 3.0: Reconciliacion Multi-Pagina FB -> IG "
            "(Mas Reciente Primero)"
        )
    )
    parser.add_argument("--dry-run", action="store_true", help="Solo muestra lo que rescataria.")
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
            wait_time = 600  # 10 minutos si habia backlog
            logging.info("Backlog pendiente detectado. Reintentando en 10 minutos...")
        else:
            wait_time = 86400  # 24 horas si todo esta al dia
            logging.info("Todo al dia. Durmiendo 24 horas hasta el proximo escaneo diario...")

        time.sleep(wait_time)


if __name__ == "__main__":
    main()
