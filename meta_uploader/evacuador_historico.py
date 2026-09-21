import json
import logging
import time
import os
import requests
from pathlib import Path

from meta_uploader import (
    check_ig_publish_limit,
    ensure_ig_compatibility,
    probe_video,
    wait_for_ig_container,
    publish_ig_container,
    _create_ig_video_container,
    upload_ig_binary,
    create_ig_media_container_from_url
)
from fb_to_ig_vigia import CAPTION_SIGNATURE, register_processed_post, load_history, load_dedupe_registry

BASE_DIR = Path(__file__).resolve().parent
REPORT_FILE = BASE_DIR / "missing_crossposts_report.json"
MAX_DAILY_UPLOADS = 40  # Margen conservador para no competir con el Vigía (limite total IG es ~50)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - [EVACUADOR HISTÓRICO] - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler(BASE_DIR / "evacuador_historico.log", encoding="utf-8"),
        logging.StreamHandler(),
    ],
)

def load_missing_queue():
    if not REPORT_FILE.exists():
        logging.error("No se encontró el reporte de faltantes. Ejecuta audit_crosspost.py primero.")
        return None
    try:
        with open(REPORT_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data
    except Exception as e:
        logging.error("Error al cargar el reporte: %s", e)
        return None

def save_missing_queue(data):
    try:
        with open(REPORT_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    except Exception as e:
        logging.error("Error al guardar el reporte actualizado: %s", e)

def process_one_historical_post():
    data = load_missing_queue()
    if not data or not data.get("missing_posts"):
        logging.info("¡Felicidades! No hay más posts históricos pendientes.")
        return False

    if not check_ig_publish_limit():
        logging.warning("Límite de API de Instagram alcanzado o muy cercano. Abortando ciclo histórico para priorizar posts frescos.")
        return False

    missing_posts = data["missing_posts"]
    
    # OPCIÓN B por defecto: procesar el más reciente del backlog primero.
    # El reporte ya viene ordenado de más reciente a más antiguo si fetch_all_fb_posts usó reverse=True.
    post_data = missing_posts.pop(0)
    
    post_id = post_data["post_id"]
    src_page = post_data["page"]
    caption = post_data.get("caption", "")
    
    logging.info("Intentando subir post histórico de %s (creado: %s): %s", src_page, post_data.get("created_time"), post_id)
    
    # Como el post_data del json no tiene los URLs de la media (solo sabíamos que faltaba),
    # tenemos que volver a pedir el post individual a FB para obtener los attachments completos
    from meta_uploader import FB_PAGE_TOKEN, FB_PAGE_ID
    import os
    
    token = os.environ.get("META_FB_PAGE_TOKEN_TEASER") if "Shirabyoshi" in src_page else os.environ.get("META_FB_PAGE_TOKEN", FB_PAGE_TOKEN)
    
    url = f"https://graph.facebook.com/v21.0/{post_id}?fields=message,full_picture,attachments{{media,subattachments,type}}&access_token={token}"
    resp = requests.get(url, timeout=30)
    if resp.status_code != 200:
        logging.error("No se pudo obtener el post de la API de FB. Volviendo a encolar. Status: %s", resp.status_code)
        # Volvemos a meterlo al inicio de la cola
        missing_posts.insert(0, post_data)
        save_missing_queue(data)
        return False
        
    full_post = resp.json()
    from fb_to_ig_vigia import extract_media_list
    media_items, original_caption = extract_media_list(full_post)
    
    if not media_items:
        logging.info("El post histórico %s no tiene media extraíble. Descartando.", post_id)
        data["total_missing_in_ig"] = len(missing_posts)
        save_missing_queue(data)
        return True
        
    final_caption = (original_caption or "").strip() + CAPTION_SIGNATURE
    at_least_one_success = False
    
    for idx, item in enumerate(media_items):
        targets = ["REELS"] if item["type"] == "VIDEO" else ["FEED"]
        temp_file = None
        local_path = None
        
        try:
            if item["type"] == "VIDEO":
                temp_file = BASE_DIR / f"temp_hist_{post_id}_{idx}.mp4"
                logging.info("Descargando video histórico...")
                with requests.get(item["url"], stream=True, timeout=60) as r:
                    with open(temp_file, "wb") as f:
                        for chunk in r.iter_content(chunk_size=8192):
                            f.write(chunk)
                            
                local_path = ensure_ig_compatibility(str(temp_file), force_recode=True)
                vinfo = probe_video(local_path)
                duration = vinfo.get("duration_seconds", 0)
                
                if duration > 90:
                    logging.info("Video histórico > 90s, activando FEED además de REELS.")
                    targets.append("FEED")
                    
            for target_type in targets:
                if not check_ig_publish_limit():
                    logging.warning("Límite IG alcanzado en medio del procesamiento de un carrusel/múltiples targets.")
                    break
                    
                path_for_target = local_path
                if item["type"] == "VIDEO":
                    if target_type == "REELS" and duration > 90:
                        path_for_target = ensure_ig_compatibility(local_path, max_duration=90)
                    
                    creation_id = _create_ig_video_container(
                        "REELS", caption=final_caption, share_to_feed=True
                    ) if target_type in ("REELS", "FEED") else None
                    
                    if creation_id:
                        time.sleep(2)
                        if upload_ig_binary(creation_id, path_for_target) and wait_for_ig_container(creation_id):
                            if publish_ig_container(creation_id):
                                logging.info("Post histórico %s subido a IG %s", post_id, target_type)
                                at_least_one_success = True
                else:
                    # Es IMAGEN
                    creation_id = create_ig_media_container_from_url(
                        item["url"], "IMAGE", final_caption, target=target_type
                    )
                    if creation_id and wait_for_ig_container(creation_id):
                        if publish_ig_container(creation_id):
                            logging.info("Imagen histórica %s subida a IG %s", post_id, target_type)
                            at_least_one_success = True
                            
        except Exception as e:
            logging.error("Error procesando media de post %s: %s", post_id, e)
            
        finally:
            if local_path and os.path.exists(local_path):
                try: os.remove(local_path)
                except: pass
            if temp_file and str(temp_file) != local_path and os.path.exists(str(temp_file)):
                try: os.remove(str(temp_file))
                except: pass
                
    if at_least_one_success:
        history = load_history()
        registry = load_dedupe_registry()
        register_processed_post(history, registry, post_id, remember_keys=False)
        data["total_missing_in_ig"] = len(missing_posts)
        save_missing_queue(data)
        logging.info("Evacuación del post %s completada exitosamente.", post_id)
        return True
    else:
        logging.error("Fallo total en la evacuación del post %s. Se encolará al final para reintento futuro.", post_id)
        missing_posts.append(post_data)
        save_missing_queue(data)
        return False

def main():
    try:
        process_one_historical_post()
    except Exception as e:
        logging.error("Excepción en ciclo del evacuador histórico: %s", e)

if __name__ == "__main__":
    main()
