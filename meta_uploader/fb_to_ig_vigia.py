import json
import logging
import time
import argparse
import os
from pathlib import Path

# Importamos motores del uploader base
from meta_uploader import (
    FB_PAGE_ID,
    IG_USER_ID,
    get_facebook_page_feed,
    get_instagram_user_feed,
    wait_for_ig_container,
    publish_ig_container,
    check_ig_publish_limit,
    ensure_ig_compatibility,
    probe_video
)

BASE_DIR = Path(__file__).resolve().parent
HISTORY_FILE = BASE_DIR / "crosspost_history.json"
POLL_INTERVAL_SECONDS = 86400  # Cambiado a 24 horas (Daily) conforme a solicitud
CAPTION_SIGNATURE = "\n\n#PW\nSíguenos también en Facebook"

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

def save_history(history):
    try:
        with open(HISTORY_FILE, "w", encoding="utf-8") as f:
            json.dump(list(history), f, indent=2)
    except Exception as e:
        logging.error("Error al guardar historial: %s", e)

def is_already_on_instagram(fb_message, ig_feed):
    """
    Compara el mensaje de Facebook con los captions de Instagram para evitar duplicados manuales.
    Sensibilidad: Primeros 80 caracteres.
    """
    if not fb_message or not ig_feed or "data" not in ig_feed:
        return False
    
    clean_fb = fb_message.strip().lower()[:80]
    if not clean_fb:
        return False

    for ig_post in ig_feed["data"]:
        ig_caption = (ig_post.get("caption") or "").strip().lower()
        if clean_fb in ig_caption:
            return True
    return False

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
    
    # 1. Obtener feed de Instagram para reconciliar
    ig_feed = get_instagram_user_feed(limit=50) 

    new_count = 0
    after_cursor = None
    backlog_scan_active = True
    
    while backlog_scan_active:
        logging.info("Solicitando pagina de feed FB (after=%s)...", after_cursor)
        fb_feed = get_facebook_page_feed(limit=25, after=after_cursor)

        if not fb_feed or "data" not in fb_feed or not fb_feed["data"]:
            logging.info("No hay mas posts en el feed de Facebook.")
            break

        page_rescues = 0
        page_already_known = 0
        
        # Procesamos en orden cronologico inverso (mas reciente primero)
        # Pero para el backlog profundo, usualmente procesamos lo que llega
        for post in fb_feed["data"]:
            post_id = post.get("id")
            message = post.get("message", "")
            
            # Si ya esta en el historial, aumentamos el contador de conocidos
            if post_id in history:
                page_already_known += 1
                continue
            
            # Inteligencia: ¿Ya lo pusiste tu a mano en Instagram?
            if is_already_on_instagram(message, ig_feed):
                logging.info("Reconciliacion: El post %s ya parece estar en Instagram. Marcando como procesado.", post_id)
                history.add(post_id)
                page_already_known += 1
                continue

            if dry_run:
                logging.info("Dry-Run: Post %s detectado como faltante.", post_id)
                page_rescues += 1
                continue

            logging.info("Procesando rescate de post: %s", post_id)
            media_items, original_caption = extract_media_list(post)
            
            if not media_items:
                logging.info("Post %s no tiene media. Saltando.", post_id)
                history.add(post_id)
                page_already_known += 1
                continue

            # Preparar caption final con firma
            final_caption = (original_caption or "").strip() + CAPTION_SIGNATURE

            success_all = True
            for idx, item in enumerate(media_items):
                targets = ["FEED", "STORIES"]
                if item["type"] == "VIDEO":
                    targets = ["REELS", "STORIES"] 
                
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
                        logging.error("Limite IG alcanzado (25/dia). Abortando ciclo.")
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
                        if creation_id and upload_ig_binary(creation_id, path_for_target):
                            if wait_for_ig_container(creation_id):
                                ig_id = publish_ig_container(creation_id)
                                if ig_id: logging.info("Video %s publicado en IG %s", post_id, target_type)
                                else: success_all = False
                            else: success_all = False
                        else: success_all = False
                        
                        if path_for_target != local_path and os.path.exists(path_for_target):
                            try: os.remove(path_for_target)
                            except: pass
                    else:
                        from meta_uploader import create_ig_media_container_from_url
                        creation_id = create_ig_media_container_from_url(item["url"], "IMAGE", final_caption, target=target_type)
                        if creation_id and wait_for_ig_container(creation_id):
                            ig_id = publish_ig_container(creation_id)
                            if ig_id: logging.info("Imagen %s publicada en IG %s", post_id, target_type)

                if local_path and os.path.exists(local_path): 
                    try: os.remove(local_path)
                    except: pass
                if local_path != str(temp_file) and os.path.exists(str(temp_file)):
                    try: os.remove(str(temp_file))
                    except: pass

            if success_all:
                history.add(post_id)
                page_rescues += 1
                save_history(history)
            
            # Si hemos procesado items exitosamente en esta pagina, aumentamos contador global
            new_count += page_rescues

        # Logica de paginacion: 
        # Si todos los posts de esta pagina ya eran conocidos, dejamos de escanear el pasado.
        if page_already_known == len(fb_feed["data"]):
            logging.info("Pagina completa ya conocida. Backlog reconciliado.")
            break
            
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

if __name__ == "__main__":
    main()
