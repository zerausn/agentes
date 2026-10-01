"""
fb_to_ig_vigia_720.py  (VERSION BASH-LOOP — sin time.sleep interno)
Crossposta UN SOLO post de Facebook a Instagram y retorna.
El loop/pausa de 720s lo gestiona el script bash (con termux-wake-lock).
Exit codes:
  0  — post crossposteado OK
  2  — no habia posts nuevos pendientes
  1  — error durante el proceso
"""
import argparse
import json
import logging
import os
import re
import sys
import time
import unicodedata
from pathlib import Path

from meta_uploader import (
    FB_PAGE_ID,
    IG_USER_ID,
    get_facebook_page_feed,
    get_instagram_library_batch,
    wait_for_ig_container,
    publish_ig_container,
    check_ig_publish_limit,
    ensure_ig_compatibility,
    probe_video
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

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - [VIGIA-720] - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler(BASE_DIR / "fb_to_ig_vigia.log", encoding="utf-8"),
        logging.StreamHandler()
    ]
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

#     marker = _normalize_marker(raw)
#     if marker:
#         keys.add(f"text:{marker}")

    normalized_raw = _strip_accents(raw)
#     for pattern in STEM_PATTERNS:
#         for match in pattern.findall(normalized_raw):
#             keys.add(f"stem:{_normalize_stem(match)}")

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


def try_crosspost_one(post, registry, ig_catalog_keys, history, dry_run=False):
    """
    Intenta crosspostear UN post.
    Retorna True si se crossposteo exitosamente, False si no.
    """
    import requests
    from meta_uploader import (
        _create_ig_video_container,
        upload_ig_binary,
        publish_ig_container,
        create_ig_media_container_from_url,
    )

    post_id = post.get("id")
    message = post.get("message", "")

    duplicate, content_keys, duplicate_reason = find_duplicate_reason(
        post_id, message, registry, ig_catalog_keys,
    )

    if duplicate:
        logging.info("Post %s omitido por duplicado (%s).", post_id, duplicate_reason)
        register_processed_post(history, registry, post_id, content_keys, remember_keys=True)
        return False

    logging.info("Procesando rescate de post: %s", post_id)

    if dry_run:
        logging.info("Dry-Run: Post %s detectado como pendiente. Claves=%s", post_id, sorted(content_keys))
        return True

    media_items, original_caption = extract_media_list(post)

    if not media_items:
        logging.info("Post %s no tiene media. Saltando.", post_id)
        register_processed_post(history, registry, post_id, remember_keys=False)
        return False

    final_caption = (original_caption or "").strip() + CAPTION_SIGNATURE

    final_caption = (original_caption or "").strip() + CAPTION_SIGNATURE

    at_least_one_success = False

    # Funcion auxiliar para limpiar temporales
    def cleanup_temps(temps):
        for path in temps:
            if path and os.path.exists(path):
                try: os.remove(path)
                except: pass

    # --- SEPARACION DE MEDIA ---
    photo_items = [item for item in media_items if item["type"] != "VIDEO"]
    video_items = [item for item in media_items if item["type"] == "VIDEO"]

    if len(photo_items) == 1:
        video_items.append(photo_items[0])
        photo_items = []

    # --- LOGICA DE CARRUSEL (Solo para multiples fotos) ---
    if len(photo_items) > 1:
        logging.info("Multiples fotos detectadas (%s). Agrupando en carruseles (max 20 fotos)...", len(photo_items))
        from meta_uploader import create_ig_carousel_item, create_ig_carousel
        
        # Agrupar en chunks de maximo 20 fotos
        CHUNK_SIZE = 20
        chunks = [photo_items[i:i + CHUNK_SIZE] for i in range(0, len(photo_items), CHUNK_SIZE)]
        
        for chunk_idx, chunk in enumerate(chunks):
            if not check_ig_publish_limit():
                logging.error("Limite oficial de Instagram alcanzado. Abortando carruseles restantes.")
                break
                
            logging.info("Procesando chunk de carrusel %s/%s con %s fotos...", chunk_idx + 1, len(chunks), len(chunk))
            
            children_ids = []
            temps_to_cleanup = []
            chunk_success = True
            
            for idx, item in enumerate(chunk):
                item_url = item["url"]
                logging.info("  -> Creando contenedor foto %s/%s", idx + 1, len(chunk))
                child_id = create_ig_carousel_item(item_url, media_type="IMAGE")
                
                if child_id:
                    children_ids.append(child_id)
                else:
                    logging.warning("  -> Fallo al crear foto %s/%s de carrusel.", idx + 1, len(chunk))
                    chunk_success = False
                    break
                    
            if not chunk_success or not children_ids:
                logging.error("No se pudieron crear todos los items del carrusel %s. Abortando este carrusel.", chunk_idx + 1)
                cleanup_temps(temps_to_cleanup)
                continue
                
            # Esperar a que los contenedores hijos procesen
            logging.info("Esperando estabilizacion de contenedores hijos...")
            all_children_ready = True
            for child_id in children_ids:
                if not wait_for_ig_container(child_id):
                    all_children_ready = False
                    break
                    
            if not all_children_ready:
                logging.error("Al menos un contenedor hijo no se proceso. Abortando carrusel.")
                continue
                
            # Crear y publicar contenedor maestro
            logging.info("Creando contenedor maestro de carrusel de fotos con %s hijos...", len(children_ids))
            carousel_id = create_ig_carousel(children_ids, final_caption)
            
            if carousel_id and wait_for_ig_container(carousel_id):
                ig_id = publish_ig_container(carousel_id)
                if ig_id:
                    logging.info("Carrusel publicado en IG: %s", ig_id)
                    at_least_one_success = True
                else:
                    logging.error("Fallo la publicacion final del carrusel.")
            else:
                logging.error("Fallo la creacion del contenedor maestro de carrusel.")
                
            cleanup_temps(temps_to_cleanup)

    # --- LOGICA INDIVIDUAL (Videos o 1 sola foto) ---
    for idx, item in enumerate(video_items):
        targets = ["FEED"]
        if item["type"] == "VIDEO":
            targets = ["REELS"]

        local_path = None
        try:
            logging.info("Descargando media para optimizacion local...")
            temp_file = BASE_DIR / f"temp_vigia_{post_id}_{idx}.mp4"
            import requests
            resp = requests.get(item["url"], stream=True, timeout=30)

            with open(temp_file, "wb") as f:
                for chunk_data in resp.iter_content(chunk_size=8192):
                    f.write(chunk_data)

            local_path = ensure_ig_compatibility(str(temp_file), force_recode=False)
            vinfo = probe_video(local_path)
            duration = vinfo.get("duration_seconds", 0)

            active_targets = list(targets)
            if duration > 90:
                logging.info("Video largo detectado (%.2fs): Activando estrategia de Post de Feed Completo.", duration)
                if "FEED" not in active_targets:
                    active_targets.append("FEED")
        except Exception as e:
            logging.error("Fallo descarga/optimizacion local: %s", e)
            active_targets = []

        for target_type in active_targets:
            if not check_ig_publish_limit():
                logging.error("Limite oficial de Instagram de la API alcanzado.")
                break

            logging.info("Subiendo item %s/%s a IG %s (Binario)...", idx + 1, len(video_items), target_type)
            path_for_target = local_path

            if target_type == "STORIES" and item["type"] == "VIDEO":
                path_for_target = ensure_ig_compatibility(local_path, max_duration=60)
            elif target_type == "REELS" and duration > 90:
                logging.info("Recortando Reel a 90s para asegurar aceptacion de Meta.")
                path_for_target = ensure_ig_compatibility(local_path, max_duration=90)
            elif target_type == "FEED":
                path_for_target = local_path

            creation_id = None
            from meta_uploader import _create_ig_video_container, upload_ig_binary, create_ig_media_container_from_url
            
            if target_type == "REELS":
                creation_id = _create_ig_video_container("REELS", caption=final_caption, share_to_feed=True)
            elif target_type == "STORIES":
                if item["type"] == "VIDEO":
                    creation_id = _create_ig_video_container("STORIES")
            elif target_type == "FEED":
                creation_id = _create_ig_video_container("REELS", caption=final_caption, share_to_feed=True)

            if item["type"] == "VIDEO":
                if creation_id:
                    upload_ok = False
                    fallback_path = None
                    for attempt in range(2):
                        current_path = path_for_target if attempt == 0 else fallback_path
                        logging.info("Contenedor %s listo. Esperando estabilizacion... (intento %s/2)", target_type, attempt + 1)
                        time.sleep(2)
                        if not upload_ig_binary(creation_id, current_path):
                            logging.warning("Upload binario fallo (intento %s/2)", attempt + 1)
                            if attempt == 0:
                                logging.info("Reintentando con recode CRF 18...")
                                fallback_path = ensure_ig_compatibility(local_path, force_recode=True, crf_value=18)
                                if target_type == "REELS":
                                    creation_id = _create_ig_video_container("REELS", caption=final_caption, share_to_feed=True)
                                elif target_type == "STORIES":
                                    creation_id = _create_ig_video_container("STORIES")
                                elif target_type == "FEED":
                                    creation_id = _create_ig_video_container("REELS", caption=final_caption, share_to_feed=True)
                                if not creation_id:
                                    logging.error("No se pudo recrear contenedor para fallback.")
                                    break
                            continue
                        if wait_for_ig_container(creation_id):
                            ig_id = publish_ig_container(creation_id)
                            if ig_id:
                                logging.info("Video %s publicado en IG %s", post_id, target_type)
                                at_least_one_success = True
                                upload_ok = True
                                break
                        else:
                            logging.warning("Contenedor IG no listo (intento %s/2)", attempt + 1)

                    if upload_ok and fallback_path is not None and fallback_path != path_for_target and os.path.exists(fallback_path):
                        try: os.remove(fallback_path)
                        except: pass

                    if path_for_target != local_path and os.path.exists(path_for_target):
                        try: os.remove(path_for_target)
                        except: pass
            else:
                creation_id = create_ig_media_container_from_url(item["url"], "IMAGE", final_caption, target=target_type)
                if creation_id and wait_for_ig_container(creation_id):
                    ig_id = publish_ig_container(creation_id)
                    if ig_id:
                        logging.info("Imagen %s publicada en IG %s", post_id, target_type)
                        at_least_one_success = True

        if local_path and os.path.exists(local_path):
            try: os.remove(local_path)
            except: pass
        if local_path != str(temp_file) and os.path.exists(str(temp_file)):
            try: os.remove(str(temp_file))
            except: pass

    if at_least_one_success:
        register_processed_post(history, registry, post_id, content_keys, remember_keys=True)
        ig_catalog_keys.update(content_keys)
        return True

    return False


def process_one_post(dry_run=False):
    """
    Escanea el feed de Facebook hasta encontrar y crosspostear UN post.
    Retorna True si se encontro un post pendiente (o se crossposteo), False si no habia nada nuevo.
    """
    logging.info("--- VIGIA 720: Buscando 1 post para crosspostear (dry_run=%s) ---", dry_run)
    history = load_history()
    registry = load_dedupe_registry()
    registry["processed_post_ids"].update(history)

    ig_catalog = get_instagram_library_batch(max_pages=150, use_cache=True)
    if ig_catalog is None:
        logging.error("Fallo critico: No se pudo sincronizar el catalogo de Instagram.")
        return False

    ig_catalog_keys = build_catalog_key_index(ig_catalog)
    logging.info("Catalogo IG: %s captions, %s claves.", len(ig_catalog), len(ig_catalog_keys))

    after_cursor = None
    while True:
        logging.info("Solicitando pagina de feed FB (after=%s)...", after_cursor)
        fb_feed = get_facebook_page_feed(limit=5, after=after_cursor)

        if fb_feed is None:
            logging.error("Fallo critico: No se pudo obtener el feed de Facebook.")
            return False

        if "data" not in fb_feed or not fb_feed["data"]:
            logging.info("No hay mas posts en el feed de Facebook.")
            return False

        for post in fb_feed["data"]:
            success = try_crosspost_one(post, registry, ig_catalog_keys, history, dry_run=dry_run)
            if success:
                return True

        after_cursor = (fb_feed.get("paging") or {}).get("cursors", {}).get("after")
        if not after_cursor:
            logging.info("No hay mas paginas.")
            return False


def main():
    parser = argparse.ArgumentParser(description="Vigia Meta 720: Crosspostea 1 post FB->IG por ciclo")
    parser.add_argument("--dry-run", action="store_true", help="Solo muestra lo que crosspostearia.")
    args = parser.parse_args()

    logging.info("=" * 60)
    logging.info("  FB-to-IG VIGIA 720 (1 post/ciclo)")
    if args.dry_run:
        logging.info("  *** DRY RUN — no se publicara nada ***")
    logging.info("=" * 60)

    try:
        rescued = process_one_post(dry_run=args.dry_run)
    except Exception as e:
        logging.error("Error en pulso del Vigia 720: %s", e)
        sys.exit(1)

    if rescued:
        logging.info("Post crossposteado exitosamente. Bash hara pausa de 720s.")
        sys.exit(0)
    else:
        logging.info("No habia posts nuevos para crosspostear.")
        sys.exit(2)


if __name__ == "__main__":
    main()
