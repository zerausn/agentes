"""
album_diario.py
================
Crea álbumes diarios en Facebook y publica un teaser inmediato.

Por cada fecha:
  1. Crea álbum "Fotos YYYY-MM-DD"
  2. Sube TODAS las fotos al álbum
  3. Publica un post teaser inmediato con:
     - 5 fotos del álbum en carrusel
     - Link al álbum
     - Linktree
     - Hashtags
  4. Mueve fotos a fotos_subidas_album/
"""

import json
import logging
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from datetime import datetime
from pathlib import Path

import requests

BASE_DIR = Path(__file__).resolve().parent
PARENT_DIR = BASE_DIR.parent

LOG_FILE = BASE_DIR / "album_diario.log"
HISTORIAL_FILE = BASE_DIR / "album_diario_historial.json"
WEB_INVENTORY_FILE = Path.home() / "Desktop" / "subir fotos" / "albumes_remotos_web.json"

DIR_FOTOS = Path(r"/media/zerausn/D69493CF9493B08B/Users/ZN-/Documents/ADM/Carpeta 1/Fotos")
DIR_PROCESADAS = Path(r"/media/zerausn/D69493CF9493B08B/Users/ZN-/Documents/ADM/Carpeta 1/fotos_subidas_album")

GRAPH_API_VERSION = "v19.0"
GRAPH_URL = f"https://graph.facebook.com/{GRAPH_API_VERSION}"

SUPPORTED_EXTS = {".jpg", ".jpeg", ".png", ".webp"}
RAW_EXTS = {".dng"}
HASHTAGS = "#PW #HQ #P"

LINKTREE_URL = "https://linktr.ee/performaticwritingscali"

TEASER_COUNT = 5
CONFIRM_ATTEMPTS = 6
CONFIRM_WAIT_SECONDS = 5
GRAPH_IDS_CHUNK_SIZE = 50

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE, encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ],
)


def formatear_duracion(segundos):
    segundos = max(0, int(segundos))
    horas, resto = divmod(segundos, 3600)
    minutos, segundos = divmod(resto, 60)
    if horas:
        return f"{horas}h {minutos}m {segundos}s"
    if minutos:
        return f"{minutos}m {segundos}s"
    return f"{segundos}s"


def registrar_progreso_album(fecha, actual, total, inicio):
    porcentaje = (actual / total * 100) if total else 0
    restantes = max(0, total - actual)
    transcurrido = time.monotonic() - inicio
    eta = (transcurrido / actual * restantes) if actual else 0
    logging.info(
        "[progreso.album] %s: %s/%s fotos (%.1f%%), faltan %s, transcurrido %s, ETA %s",
        fecha,
        actual,
        total,
        porcentaje,
        restantes,
        formatear_duracion(transcurrido),
        formatear_duracion(eta),
    )


def peso_archivo(path):
    try:
        return path.stat().st_size
    except OSError:
        return 0


def seleccionar_fotos_teaser(fotos, cantidad=TEASER_COUNT):
    if len(fotos) <= cantidad:
        return list(fotos)

    seleccionadas = []
    total = len(fotos)
    for indice in range(cantidad):
        inicio = indice * total // cantidad
        fin = (indice + 1) * total // cantidad
        segmento = fotos[inicio:fin] or [fotos[min(inicio, total - 1)]]
        seleccionadas.append(max(segmento, key=peso_archivo))

    logging.info(
        "[teaser] Fotos seleccionadas para carrusel: %s",
        ", ".join(foto.name for foto in seleccionadas),
    )
    return seleccionadas


def crear_caption_teaser(fecha, album_url):
    fecha_legible = datetime.strptime(fecha, "%Y-%m-%d").strftime("%b %d, %Y")
    return (
        f"New gallery: a night from the performative archive in Cali.\n\n"
        f"Photos from {fecha_legible} are now live.\n"
        f"Full album: {album_url}\n"
        f"{LINKTREE_URL}\n\n"
        f"Which photo should become the cover?\n\n"
        f"{HASHTAGS}"
    )


def crear_caption_foto(stem):
    return (
        f"From the performative archive in Cali.\n"
        f"Archive frame: {stem}\n\n"
        f"{HASHTAGS}"
    )


def _load_env():
    env_path = PARENT_DIR / ".env"
    env = {}
    if not env_path.exists():
        return env
    with open(env_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            env[key.strip()] = value.strip().strip('"').strip("'")
    return env


ENV = _load_env()
FB_PAGE_ID = ENV.get("META_FB_PAGE_ID", "")
FB_TOKEN = ENV.get("META_FB_PAGE_TOKEN", "")


def debug_token(token):
    r = requests.get(
        "https://graph.facebook.com/debug_token",
        params={"input_token": token, "access_token": token},
        timeout=30,
    )
    data = r.json()
    return data.get("data", {})


def derivar_page_token(token):
    r = requests.get(
        f"{GRAPH_URL}/{FB_PAGE_ID}",
        params={"fields": "access_token", "access_token": token},
        timeout=30,
    )
    data = r.json()
    return data.get("access_token")


def asegurar_page_token():
    global FB_TOKEN

    try:
        info = debug_token(FB_TOKEN)
    except requests.RequestException as e:
        logging.error("[auth] No se pudo diagnosticar el token sin exponerlo: %s", e.__class__.__name__)
        return False

    token_type = info.get("type")
    if token_type == "PAGE" and info.get("is_valid"):
        logging.info("[auth] META_FB_PAGE_TOKEN validado como PAGE.")
        return True

    if token_type == "USER" and info.get("is_valid"):
        logging.warning("[auth] META_FB_PAGE_TOKEN es USER; derivando Page Access Token en memoria.")
        try:
            page_token = derivar_page_token(FB_TOKEN)
            page_info = debug_token(page_token) if page_token else {}
        except requests.RequestException as e:
            logging.error("[auth] No se pudo derivar Page Access Token: %s", e.__class__.__name__)
            return False

        if page_info.get("type") == "PAGE" and page_info.get("is_valid"):
            FB_TOKEN = page_token
            logging.info("[auth] Page Access Token derivado y validado para esta corrida.")
            return True

    logging.error("[auth] Token invalido para endpoints de pagina: type=%s valid=%s", token_type, info.get("is_valid"))
    return False


def cargar_json(path):
    if not path.exists():
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def guardar_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def extraer_fecha(nombre):
    m = re.match(r"(\d{8})", nombre)
    if m:
        y, mo, d = m.group(1)[:4], m.group(1)[4:6], m.group(1)[6:8]
        return f"{y}-{mo}-{d}"
    return None


def cargar_albumes_web():
    """Lee el inventario completo de albumes guardado por Fase 1 (Edge + API)."""
    if not WEB_INVENTORY_FILE.exists():
        return {}
    try:
        data = json.loads(WEB_INVENTORY_FILE.read_text(encoding="utf-8"))
        result = {}
        for entry in data.get("albumes", []):
            name = entry.get("name")
            album_id = entry.get("id")
            if name and album_id:
                result[name] = album_id
        if result:
            logging.info("[album.web] %s album(s) cargados desde inventario de Fase 1 (API+Edge)", len(result))
        return result
    except Exception as e:
        logging.warning("[album.web] No se pudo leer %s: %s", WEB_INVENTORY_FILE.name, e)
        return {}


def convertir_dng_a_jpeg(dng_path, jpeg_path):
    logging.info("[dng] Convirtiendo %s ...", dng_path.name)
    try:
        r = subprocess.run(["dcraw", "-c", str(dng_path)],
                           capture_output=True, timeout=120, check=True)
        subprocess.run(["convert", "-", "-quality", "100", str(jpeg_path)],
                       input=r.stdout, capture_output=True, timeout=60, check=True)
        if jpeg_path.exists() and jpeg_path.stat().st_size > 0:
            logging.info("[dng] OK: %s -> %s (%.1f MB)",
                         dng_path.name, jpeg_path.name,
                         jpeg_path.stat().st_size / 1_000_000)
            return True
    except Exception as e:
        logging.error("[dng] Error con %s: %s", dng_path.name, e)
    return False


_albumes_fallidos: set = set()


def crear_album(nombre):
    if nombre in _albumes_fallidos:
        logging.warning("[album] Saltando '%s' (ya falló anteriormente en esta sesión).", nombre)
        return None
    logging.info("[album] Creando '%s' ...", nombre)
    url = f"{GRAPH_URL}/{FB_PAGE_ID}/albums"
    payload = {"name": nombre, "access_token": FB_TOKEN}
    for i in range(3):
        try:
            r = requests.post(url, data=payload, timeout=30)
            data = r.json()
            if "id" in data:
                logging.info("[album] Creado: '%s' -> id=%s", nombre, data["id"])
                return data["id"]
            if "error" in data:
                err = data["error"]
                if "duplicate" in str(err).lower():
                    albumes = listar_albumes()
                    if nombre in albumes:
                        return albumes[nombre]
                logging.warning("[album] Error (intento %s/3): %s", i + 1, err.get("message"))
        except Exception as e:
            logging.warning("[album] Exception (intento %s/3): %s", i + 1, e)
        time.sleep(3 * (i + 1))
    logging.error("[album] Falló crear '%s' 3 veces. No se reintentará en esta sesión.", nombre)
    _albumes_fallidos.add(nombre)
    return None


def listar_albumes():
    albumes = {}
    url_base = f"{GRAPH_URL}/{FB_PAGE_ID}/albums"
    
    for intento in range(1, 4):
        url = url_base
        params = {"access_token": FB_TOKEN, "limit": "100", "fields": "id,name"}
        temp_albumes = {}
        exito = True
        
        try:
            while url:
                r = requests.get(url, params=params if "?" not in url else {}, timeout=30)
                data = r.json()
                
                if "error" in data:
                    logging.warning("[album] Error listando álbumes remotos (intento %s/3): %s", 
                                    intento, data["error"].get("message"))
                    exito = False
                    break
                    
                for a in data.get("data", []):
                    temp_albumes[a["name"]] = a["id"]
                    
                url = data.get("paging", {}).get("next", "")
                
        except Exception as e:
            logging.warning("[album] Exception listando álbumes (intento %s/3): %s", intento, e)
            exito = False
            
        if exito:
            return temp_albumes
            
        time.sleep(3 * intento)
        
    logging.error("[album] Imposible listar álbumes después de 3 intentos. Abortando para evitar duplicados.")
    raise RuntimeError("No se pudo obtener la lista de álbumes remotos de Facebook.")


def graph_get(path, params=None, timeout=30):
    payload = dict(params or {})
    payload["access_token"] = FB_TOKEN
    r = requests.get(f"{GRAPH_URL}/{path}", params=payload, timeout=timeout)
    return r.json()


def chunks(items, size):
    for start in range(0, len(items), size):
        yield items[start:start + size]


def confirmar_ids_remotos(ids, fields, album_id=None):
    if not ids:
        return True

    for grupo in chunks(ids, GRAPH_IDS_CHUNK_SIZE):
        data = graph_get("", {"ids": ",".join(grupo), "fields": fields})
        for item_id in grupo:
            item = data.get(item_id)
            if not item or "error" in item or item.get("id") != item_id:
                logging.warning("[confirm] ID no confirmado en Facebook: %s", item_id)
                return False
            if album_id and item.get("album", {}).get("id") != album_id:
                logging.warning("[confirm] Foto %s no figura dentro del album %s.", item_id, album_id)
                return False
    return True


def confirmar_album_remoto(album_id, nombre_album):
    data = graph_get(album_id, {"fields": "id,name,count,link"})
    if data.get("id") != album_id:
        logging.warning("[confirm] Album no accesible todavia: %s", album_id)
        return False
    if data.get("name") != nombre_album:
        logging.warning("[confirm] Album inesperado: esperado='%s' recibido='%s'", nombre_album, data.get("name"))
        return False
    return True


def confirmar_teaser_remoto(post_id):
    if not post_id:
        logging.warning("[confirm] No hay ID de teaser para confirmar.")
        return False
    data = graph_get(post_id, {"fields": "id,is_published,created_time,permalink_url"})
    if data.get("id") != post_id:
        logging.warning("[confirm] Teaser no accesible todavia: %s", post_id)
        return False
    if data.get("is_published") is not True:
        logging.warning("[confirm] Teaser existe pero no figura publicado todavia: %s", post_id)
        return False
    return True


def confirmar_album_publicado(album_id, nombre_album, foto_ids, teaser_post_id):
    for intento in range(1, CONFIRM_ATTEMPTS + 1):
        try:
            album_ok = confirmar_album_remoto(album_id, nombre_album)
            fotos_ok = confirmar_ids_remotos(foto_ids, "id,created_time,link,album", album_id=album_id)
            teaser_ok = confirmar_teaser_remoto(teaser_post_id)
        except requests.RequestException as e:
            logging.warning("[confirm] Error de red sin exponer token (intento %s/%s): %s",
                            intento, CONFIRM_ATTEMPTS, e.__class__.__name__)
            album_ok = fotos_ok = teaser_ok = False

        if album_ok and fotos_ok and teaser_ok:
            logging.info("[confirm] Facebook confirmó álbum, %s foto(s) y teaser publicado.", len(foto_ids))
            return True

        if intento < CONFIRM_ATTEMPTS:
            logging.info("[confirm] Esperando procesamiento remoto (%s/%s)...",
                         intento, CONFIRM_ATTEMPTS)
            time.sleep(CONFIRM_WAIT_SECONDS)

    logging.error("[confirm] No se pudo confirmar publicación completa del álbum %s.", nombre_album)
    return False


def subir_foto_a_album(album_id, foto_path, mensaje):
    logging.info("[album.foto] Subiendo %s ...", foto_path.name)
    url = f"{GRAPH_URL}/{album_id}/photos"
    for i in range(3):
        try:
            with open(foto_path, "rb") as f:
                files = {"source": (foto_path.name, f, "image/jpeg")}
                data = {"message": mensaje, "access_token": FB_TOKEN}
                r = requests.post(url, files=files, data=data, timeout=120)
                resp = r.json()
                if "id" in resp:
                    return resp["id"]
                if "error" in resp:
                    logging.warning("[album.foto] Error (intento %s/3): %s",
                                    i + 1, resp["error"].get("message"))
        except Exception as e:
            logging.warning("[album.foto] Exception (intento %s/3): %s", i + 1, e)
        time.sleep(5 * (i + 1))
    return None


def subir_foto_temp(foto_path):
    url = f"{GRAPH_URL}/{FB_PAGE_ID}/photos"
    for i in range(3):
        try:
            with open(foto_path, "rb") as f:
                files = {"source": (foto_path.name, f, "image/jpeg")}
                data = {"published": "false", "access_token": FB_TOKEN}
                r = requests.post(url, files=files, data=data, timeout=120)
                resp = r.json()
                if "id" in resp:
                    return resp["id"]
        except Exception:
            pass
        time.sleep(3)
    return None


def publicar_post_carrusel(media_ids, mensaje):
    url = f"{GRAPH_URL}/{FB_PAGE_ID}/feed"
    attached = [{"media_fbid": mid} for mid in media_ids]
    payload = {
        "message": mensaje,
        "attached_media": json.dumps(attached),
        "published": "true",
        "access_token": FB_TOKEN,
    }
    for i in range(3):
        try:
            r = requests.post(url, data=payload, timeout=30)
            data = r.json()
            if "id" in data:
                logging.info("[teaser] Post publicado inmediatamente (id=%s)", data["id"])
                return data["id"]
            if "error" in data:
                logging.warning("[teaser] Error (intento %s/3): %s",
                                i + 1, data["error"].get("message"))
        except Exception as e:
            logging.warning("[teaser] Exception (intento %s/3): %s", i + 1, e)
        time.sleep(5 * (i + 1))
    return None


def procesar():
    if not FB_PAGE_ID or not FB_TOKEN:
        logging.error("Credenciales no configuradas.")
        return
    if not asegurar_page_token():
        return

    DIR_FOTOS.mkdir(parents=True, exist_ok=True)
    DIR_PROCESADAS.mkdir(parents=True, exist_ok=True)

    historial = cargar_json(HISTORIAL_FILE)

    archivos = sorted(DIR_FOTOS.iterdir(), key=lambda p: p.name)

    por_fecha = {}
    for archivo in archivos:
        if not archivo.is_file():
            continue
        ext = archivo.suffix.lower()
        if ext not in SUPPORTED_EXTS and ext not in RAW_EXTS:
            continue
        if archivo.stem in historial:
            continue
        fecha = extraer_fecha(archivo.stem)
        if not fecha:
            continue
        por_fecha.setdefault(fecha, []).append(archivo)

    if not por_fecha:
        logging.info("No hay fotos nuevas.")
        return

    albumes = listar_albumes()

    # Fusionar con los IDs confirmados por la Fase 1 (Edge web)
    albumes_web = cargar_albumes_web()
    for nombre, wid in albumes_web.items():
        if nombre not in albumes:
            logging.info("[album.web] Usando ID de Fase 1 para '%s': %s", nombre, wid)
        albumes[nombre] = wid

    for fecha in sorted(por_fecha.keys()):

        fotos = por_fecha[fecha]
        nombre_album = "Fotos sueltas" if len(fotos) == 1 else f"Fotos {fecha}"
        album_id = albumes.get(nombre_album)
        if not album_id:
            album_id = crear_album(nombre_album)
            if not album_id:
                continue
            albumes[nombre_album] = album_id
        else:
            logging.info("[album] Ya existe: '%s'", nombre_album)

        fotos = por_fecha[fecha]
        logging.info("[fecha] %s: %s foto(s)", fecha, len(fotos))

        foto_paths_subidas = []
        foto_ids_subidas = []
        inicio_album = time.monotonic()
        total_fotos_album = len(fotos)

        for indice, foto in enumerate(fotos, start=1):
            ext = foto.suffix.lower()
            foto_a_subir = foto
            es_temporal = False

            if ext in RAW_EXTS:
                tmp = tempfile.NamedTemporaryFile(suffix=".jpg", delete=False)
                jpeg_temp = Path(tmp.name)
                tmp.close()
                if not convertir_dng_a_jpeg(foto, jpeg_temp):
                    continue
                foto_a_subir = jpeg_temp
                es_temporal = True

            try:
                from PIL import Image, ImageFile, ImageOps
                ImageFile.LOAD_TRUNCATED_IMAGES = True
                Image.MAX_IMAGE_PIXELS = None
                with Image.open(foto_a_subir) as img:
                    if img.width * img.height > 40000000 or max(img.width, img.height) > 2048:
                        logging.info("[img] Redimensionando imagen gigante (%sx%s): %s", img.width, img.height, foto.name)
                        img = ImageOps.exif_transpose(img)
                        img.thumbnail((2048, 2048), getattr(getattr(Image, "Resampling", Image), "LANCZOS", 1))
                        tmp_res = tempfile.NamedTemporaryFile(suffix=".jpg", delete=False)
                        tmp_res.close()
                        img_path = Path(tmp_res.name)
                        img.convert("RGB").save(img_path, "JPEG", quality=95)
                        
                        if es_temporal:
                            os.unlink(foto_a_subir)
                        foto_a_subir = img_path
                        es_temporal = True
            except Exception as e:
                logging.warning("[img] No se pudo verificar/redimensionar %s: %s", foto.name, e)

            mensaje = crear_caption_foto(foto.stem)
            fb_id = subir_foto_a_album(album_id, foto_a_subir, mensaje)

            if es_temporal:
                try:
                    os.unlink(foto_a_subir)
                except OSError:
                    pass

            if fb_id:
                foto_paths_subidas.append(foto)
                foto_ids_subidas.append(fb_id)
                logging.info("[ok] %s subida al album (id=%s)", foto.name, fb_id)
            else:
                logging.error("[fail] No se pudo subir %s", foto.name)

            registrar_progreso_album(fecha, indice, total_fotos_album, inicio_album)
            time.sleep(2)

        if not foto_paths_subidas:
            continue

        # Publicar teaser inmediato cuando el album ya termino de subirse.
        album_url = f"https://www.facebook.com/media/set/?set=a.{album_id}"
        teaser_paths = seleccionar_fotos_teaser(foto_paths_subidas, TEASER_COUNT)
        total = len(foto_paths_subidas)

        # Subir como no-publicadas para el carrusel
        teaser_temp_ids = []
        for fp in teaser_paths[:TEASER_COUNT]:
            ext = fp.suffix.lower()
            if ext in RAW_EXTS:
                tmp2 = tempfile.NamedTemporaryFile(suffix=".jpg", delete=False)
                jpeg_t = Path(tmp2.name)
                tmp2.close()
                if convertir_dng_a_jpeg(fp, jpeg_t):
                    tid = subir_foto_temp(jpeg_t)
                    os.unlink(jpeg_t)
                else:
                    tid = None
            else:
                tid = subir_foto_temp(fp)
            if tid:
                teaser_temp_ids.append(tid)
            time.sleep(2)

        teaser_post_id = None
        if teaser_temp_ids:
            mensaje_teaser = crear_caption_teaser(fecha, album_url)
            teaser_post_id = publicar_post_carrusel(teaser_temp_ids, mensaje_teaser)

        if not confirmar_album_publicado(album_id, nombre_album, foto_ids_subidas, teaser_post_id):
            logging.error("[archive] No se mueven fotos locales de %s hasta confirmar Facebook.", nombre_album)
            continue

        # Crear carpeta local con el nombre del album y copiar fotos
        album_dir = DIR_PROCESADAS / nombre_album
        album_dir.mkdir(parents=True, exist_ok=True)
        for foto in foto_paths_subidas:
            destino = album_dir / foto.name
            shutil.copy2(str(foto), str(destino))
            logging.info("[archive] %s -> %s", foto.name, destino)

        # Mover originales a carpeta plana (legacy)
        for foto in foto_paths_subidas:
            destino_legacy = DIR_PROCESADAS / foto.name
            if not destino_legacy.exists():
                shutil.move(str(foto), str(destino_legacy))
            else:
                os.remove(str(foto))
            logging.info("[move] %s eliminado de origen", foto.name)

        historial.update({f.stem: {"album": nombre_album, "album_id": album_id,
                                    "subido": time.strftime("%Y-%m-%d %H:%M:%S")}
                          for f in foto_paths_subidas})
        guardar_json(HISTORIAL_FILE, historial)

        logging.info("[fecha] %s completada: %s fotos al album, teaser inmediato con %s fotos",
                     fecha, total, len(teaser_temp_ids))

    total_f = sum(len(por_fecha[f]) for f in por_fecha)
    logging.info("=== COMPLETADO: %s foto(s) en %s fecha(s) ===", total_f, len(por_fecha))


def main():
    print("=" * 60)
    print("  ANTIGRAVITY - ALBUM DIARIO + TEASER INMEDIATO")
    print("=" * 60)
    print(f"  Linktree : {LINKTREE_URL}")
    print(f"  Teaser   : {TEASER_COUNT} fotos")
    print("=" * 60)
    procesar()


if __name__ == "__main__":
    main()
