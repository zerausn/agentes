import json
import logging
import time
from pathlib import Path

# Importamos del uploader base y vigia
from meta_uploader import (
    get_instagram_library_batch,
    get_facebook_page_feed,
)
from fb_to_ig_vigia import (
    FB_PAGES,
    build_catalog_key_index,
    extract_content_keys,
    extract_media_list,
)

BASE_DIR = Path(__file__).resolve().parent
REPORT_FILE = BASE_DIR / "missing_crossposts_report.json"

logging.basicConfig(level=logging.INFO, format="%(asctime)s - [AUDITOR] - %(levelname)s - %(message)s")


def fetch_all_fb_posts():
    """Descarga el historial absoluto de todas las paginas de FB (sin limite de early stop)"""
    all_posts = []
    
    for page_id, page_token, page_name in FB_PAGES:
        if not page_id or not page_token:
            logging.warning("[%s] Sin credenciales — saltando pagina.", page_name)
            continue
            
        logging.info("[%s] Descargando TODO el historial de Facebook...", page_name)
        after_cursor = None
        page_num = 0
        
        while True:
            page_num += 1
            logging.info("[%s] Pagina FB %s...", page_name, page_num)
            
            fb_feed = get_facebook_page_feed(
                limit=10,  # Lotes mas grandes para que sea rapido
                after=after_cursor,
                page_id=page_id,
                page_token=page_token,
            )
            
            if fb_feed is None:
                break
                
            page_data = fb_feed.get("data") or []
            if not page_data:
                break
                
            for post in page_data:
                post["_source_page_name"] = page_name
            
            all_posts.extend(page_data)
            
            after_cursor = (fb_feed.get("paging") or {}).get("cursors", {}).get("after")
            if not after_cursor:
                break
                
    # Ordenar del mas viejo al mas nuevo, o viceversa
    all_posts.sort(key=lambda p: p.get("created_time", ""), reverse=True)
    return all_posts


def main():
    logging.info("Iniciando auditoría profunda de FB vs IG...")
    
    # 1. Obtener TODO el catálogo de Instagram
    logging.info("Descargando catálogo completo de Instagram...")
    ig_catalog = get_instagram_library_batch(max_pages=200, use_cache=False)
    if ig_catalog is None:
        logging.error("No se pudo obtener el catalogo de IG.")
        return
        
    ig_catalog_keys = build_catalog_key_index(ig_catalog)
    logging.info("Instagram tiene %s posts. %s Claves generadas.", len(ig_catalog), len(ig_catalog_keys))
    
    # 2. Obtener TODOS los posts de Facebook
    fb_posts = fetch_all_fb_posts()
    logging.info("Facebook tiene %s posts en total.", len(fb_posts))
    
    # 3. Cruzar los datos para hallar faltantes
    missing_posts = []
    
    for post in fb_posts:
        message = post.get("message", "")
        post_id = post.get("id")
        src_page = post.get("_source_page_name")
        created_time = post.get("created_time")
        
        # Filtro basico: ¿Tiene media? Si es solo texto, IG no lo acepta
        media_items, _ = extract_media_list(post)
        if not media_items:
            continue
            
        content_keys = extract_content_keys(message)
        
        # Verificamos si alguna clave de este post coincide con algo subido a IG
        ig_match = content_keys & ig_catalog_keys
        
        if not ig_match:
            # ¡Falta en Instagram!
            missing_posts.append({
                "page": src_page,
                "post_id": post_id,
                "created_time": created_time,
                "caption": message[:100] + "..." if len(message) > 100 else message,
                "media_count": len(media_items),
                "keys": list(content_keys)
            })
            
    logging.info("Auditoria completada. Faltan %s posts por subir a Instagram.", len(missing_posts))
    
    # 4. Guardar reporte
    with open(REPORT_FILE, "w", encoding="utf-8") as f:
        json.dump({
            "total_fb_scanned": len(fb_posts),
            "total_ig_scanned": len(ig_catalog),
            "total_missing_in_ig": len(missing_posts),
            "missing_posts": missing_posts
        }, f, indent=2, ensure_ascii=False)
        
    logging.info("Reporte guardado en: %s", REPORT_FILE)


if __name__ == "__main__":
    main()
