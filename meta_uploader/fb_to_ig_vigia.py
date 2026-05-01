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
POLL_INTERVAL_SECONDS = 86400  # Cambiado a 24 horas (Daily) conforme a solicitud
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
    format="%(asctime)s - [VIGIA-2.0] - %(levelname)s - %(message)s",
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
    Extrae CUALQUIER media del post. Si es un carrusel, devuelve una lista de items individuales.
    """
    items = []
    message = post.get("message", "")
    full_picture = post.get("full_picture")
    attachments = post.get("attachments", {}).get("data", [])
    
    # Caso 1: Revisar sub-attachments (Album/Carrusel)
    # El usuario quiere que cada foto del album sea un post individual.
    for att in attachments:
        sub = att.get("subattachments", {}).get("data", [])
        if sub:
            for node in sub:
                media_url = node.get("media", {}).get("source") # Para videos en sub-att
                if not media_url: # Para fotos
                    media_url = node.get("media", {}).get("image", {}).get("src")
                
                m_type = "VIDEO" if "video" in node.get("type", "") else "IMAGE"
                if media_url:
                    items.append({"url": media_url, "type": m_type})
            if items: return items, message
            
    # Caso 2: Video individual en main metadata
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

def process_new_posts(dry_run=False):
    logging.info("--- Iniciando ciclo de reconciliación FB -> IG (Escaneo Profundo) ---")
    history = load_history()
    registry = load_dedupe_registry()
    registry["processed_post_ids"].update(history)

    # 1. Obtener catálogo completo de Instagram para reconciliar, no solo los ultimos 5.
    ig_catalog = get_instagram_library_batch(max_pages=150, use_cache=True)
    if ig_catalog is None:
        logging.error("Fallo critico: No se pudo sincronizar el catalogo de Instagram. Abortando Vigia por seguridad.")
        return 0
    ig_catalog_keys = build_catalog_key_index(ig_catalog)
    logging.info(
        "Catalogo IG cargado: %s captions remotos, %s claves canonicas.",
        len(ig_catalog),
        len(ig_catalog_keys),
    )

    new_count = 0
    after_cursor = None
    backlog_scan_active = True
    
    while backlog_scan_active:
        logging.info("Solicitando pagina de feed FB (after=%s)...", after_cursor)
        fb_feed = get_facebook_page_feed(limit=5, after=after_cursor)

        if fb_feed is None:
            logging.error("Fallo critico: No se pudo obtener el feed de Facebook (API Error). Abortando ciclo.")
            break
        if "data" not in fb_feed or not fb_feed["data"]:
            logging.info("No hay mas posts en el feed de Facebook.")
            break

        page_rescues = 0
        page_already_known = 0
        
        # Procesamos en orden cronologico inverso (mas reciente primero)
        # Pero para el backlog profundo, usualmente procesamos lo que llega
        for post in fb_feed["data"]:
            post_id = post.get("id")
            message = post.get("message", "")
            

            duplicate, content_keys, duplicate_reason = find_duplicate_reason(
                post_id,
                message,
                registry,
                ig_catalog_keys,
            )
            
            # Si ya esta en el historial o si IG ya tiene el mismo contenido, lo registramos y seguimos.
            if duplicate:
                logging.info("Reconciliacion: Post %s omitido por duplicado (%s).", post_id, duplicate_reason)
                register_processed_post(history, registry, post_id, content_keys, remember_keys=True)
                page_already_known += 1
                continue

            if dry_run:
                logging.info("Dry-Run: Post %s detectado como faltante. Claves=%s", post_id, sorted(content_keys))
                page_rescues += 1
                continue

            logging.info("Procesando rescate de post: %s", post_id)
            media_items, original_caption = extract_media_list(post)
            
            if not media_items:
                logging.info("Post %s no tiene media. Saltando.", post_id)
                register_processed_post(history, registry, post_id, remember_keys=False)
                page_already_known += 1
                continue

            # Preparar caption final con firma
            final_caption = (original_caption or "").strip() + CAPTION_SIGNATURE

            at_least_one_success = False
            for idx, item in enumerate(media_items):
                targets = ["FEED"]
                if item["type"] == "VIDEO":
                    targets = ["REELS"] 
                
                from meta_uploader import ensure_ig_compatibility
                import requests

                local_path = None
                try:
                    logging.info("Descargando media para optimizacion local...")
                    temp_file = BASE_DIR / f"temp_vigia_{post_id}_{idx}.mp4"
                    resp = requests.get(item["url"], stream=True, timeout=30)

                    with open(temp_file, "wb") as f:
                        for chunk in resp.iter_content(chunk_size=8192):
                            f.write(chunk)
                    
                    local_path = ensure_ig_compatibility(str(temp_file), force_recode=True)
                    vinfo = probe_video(local_path)
                    duration = vinfo.get("duration_seconds", 0)
                    
                    active_targets = list(targets)
                    if duration > 90:
                        logging.info("Video largo detectado (%.2fs): Activando estrategia de Post de Feed Completo.", duration)
                        if "FEED" not in active_targets:
                            active_targets.append("FEED")
                except Exception as e:
                    logging.error("Fallo descarga/optimizacion local: %s", e)
                    success_all = False
                    continue

                for target_type in active_targets:
                    if not check_ig_publish_limit():
                        logging.error("Limite oficial de Instagram de la API alcanzado. Abortando ciclo temporalmente.")
                        backlog_scan_active = False # Salimos de todo el escaneo
                        success_all = False
                        break
                    
                    logging.info("Subiendo item %s/%s a IG %s (Binario)...", idx+1, len(media_items), target_type)
                    path_for_target = local_path
                    
                    if target_type == "STORIES" and item["type"] == "VIDEO":
                        path_for_target = ensure_ig_compatibility(local_path, max_duration=60)
                    elif target_type == "REELS" and duration > 90:
                        logging.info("Recortando Reel a 90s para asegurar aceptacion de Meta.")
                        path_for_target = ensure_ig_compatibility(local_path, max_duration=90)
                    elif target_type == "FEED":
                        path_for_target = local_path

                    from meta_uploader import (
                        _create_ig_video_container,
                        upload_ig_binary,
                        publish_ig_container
                    )
                    
                    creation_id = None
                    if target_type == "REELS":
                        creation_id = _create_ig_video_container("REELS", caption=final_caption, share_to_feed=True)
                    elif target_type == "STORIES":
                        if item["type"] == "VIDEO":
                            creation_id = _create_ig_video_container("STORIES")
                    elif target_type == "FEED":
                        creation_id = _create_ig_video_container("REELS", caption=final_caption, share_to_feed=True)
                    
                    if item["type"] == "VIDEO":
                        if creation_id:
                            logging.info("Contenedor %s listo. Esperando estabilizacion en Meta...", target_type)
                            time.sleep(2)  # Pausa de propagación requerida para archivos pesados
                            if upload_ig_binary(creation_id, path_for_target):
                                if wait_for_ig_container(creation_id):
                                    ig_id = publish_ig_container(creation_id)
                                    if ig_id: 
                                        logging.info("Video %s publicado en IG %s", post_id, target_type)
                                        at_least_one_success = True

                        
                        if path_for_target != local_path and os.path.exists(path_for_target):
                            try: os.remove(path_for_target)
                            except: pass
                    else:
                        from meta_uploader import create_ig_media_container_from_url
                        creation_id = create_ig_media_container_from_url(item["url"], "IMAGE", final_caption, target=target_type)
                        if creation_id and wait_for_ig_container(creation_id):
                            ig_id = publish_ig_container(creation_id)
                            if ig_id: 
                                logging.info("Imagen %s publicada en IG %s", post_id, target_type)
                                at_least_one_success = True

                if not backlog_scan_active:
                    break

                if local_path and os.path.exists(local_path): 
                    try: os.remove(local_path)
                    except: pass
                if local_path != str(temp_file) and os.path.exists(str(temp_file)):
                    try: os.remove(str(temp_file))
                    except: pass

            # Si al menos un componente del post se subio, marcamos el post entero como procesado
            # para evitar bucles de duplicados si otra parte (ej. Stories) falla.
            if at_least_one_success:
                register_processed_post(history, registry, post_id, content_keys, remember_keys=True)
                ig_catalog_keys.update(content_keys)
                page_rescues += 1
                new_count += 1

            if not backlog_scan_active:
                break
            
        # Logica de paginacion:
        # Se elimina el freno de 'pagina conocida' a peticion del usuario para 
        # realizar una barrida (Deep Scan) total del historial de Facebook cada ciclo.
        logging.info("Revision de la pagina completada. Reconciliados previamente: %s/%s", page_already_known, len(fb_feed["data"]))
            
        # Obtener cursor para la siguiente pagina
        after_cursor = (fb_feed.get("paging") or {}).get("cursors", {}).get("after")
        if not after_cursor:
            logging.info("No hay mas paginas (cursor after nulo).")
            break

        # Limite de seguridad para evitar loops infinitos en una sola corrida
        if new_count > 50:
            logging.warning("Se ha alcanzado un lote grande (50+). Pausando para goteo adaptativo.")
            break

    logging.info("Ciclo finalizado. Rescatados %s posts en total.", new_count)
    return new_count

def main():
    parser = argparse.ArgumentParser(description="Agente Vigia 3.2: Rescate y Reconciliacion FB-IG (Deep Scan)")
    parser.add_argument("--dry-run", action="store_true", help="Solo muestra lo que rescataria.")
    parser.add_argument("--once", action="store_true", help="Ejecuta una vez y sale.")
    args = parser.parse_args()

    while True:
        try:
            rescued = process_new_posts(dry_run=args.dry_run)
        except Exception as e:
            logging.error("Error en pulso del Vigia: %s", e)
            rescued = 0
        
        if args.once or args.dry_run: break
        
        if rescued > 0:
            # Si hubo trabajo, dormimos poco (Polling Adaptativo de Alta Frecuencia)
            wait_time = 600 # 10 minutos
            logging.info("Backlog pendiente detectado. Reintentando limpieza en 10 minutos...")
        else:
            # Si todo esta limpio, dormimos 24 horas (Daily Scan)
            wait_time = 86400
            logging.info("Todo al dia. Durmiendo 24 horas hasta el proximo escaneo diario...")
            
        time.sleep(wait_time)

if __name__ == "__main__":
    main()
