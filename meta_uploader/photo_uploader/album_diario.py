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
from io import BytesIO
from pathlib import Path

import requests

BASE_DIR = Path(__file__).resolve().parent
PARENT_DIR = BASE_DIR.parent

LOG_FILE = BASE_DIR / "album_diario.log"
HISTORIAL_FILE = BASE_DIR / "album_diario_historial.json"

DIR_FOTOS = Path(r"/media/zerausn/D69493CF9493B08B/Users/ZN-/Documents/ADM/Carpeta 1/Fotos")
DIR_PROCESADAS = Path(r"/media/zerausn/D69493CF9493B08B/Users/ZN-/Documents/ADM/Carpeta 1/fotos_subidas_album")

GRAPH_API_VERSION = "v19.0"
GRAPH_URL = f"https://graph.facebook.com/{GRAPH_API_VERSION}"

SUPPORTED_EXTS = {".jpg", ".jpeg", ".png", ".webp"}
RAW_EXTS = {".dng"}
HASHTAGS = "#PW #HQ #P"
REQUIRED_PAGE_SCOPES = {"pages_manage_posts", "pages_read_engagement"}
RECOMMENDED_PAGE_SCOPES = {"pages_manage_metadata", "pages_read_user_content"}

LINKTREE_URL = "https://linktr.ee/performaticwritingscali"

SINGLE_PHOTO_ALBUM_NAME = "Fotos sueltas"
TEASER_COUNT = 5
CONFIRM_ATTEMPTS = 24
CONFIRM_WAIT_SECONDS = 10
GRAPH_IDS_CHUNK_SIZE = 50
MAX_UPLOAD_EDGE = 4096
JPEG_UPLOAD_QUALITY = 95

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


def crear_caption_teaser(fecha, album_url, nombre_album=None, total_fotos=None):
    if nombre_album == SINGLE_PHOTO_ALBUM_NAME:
        return (
            f"New gallery: selected one-shot moments from the performative archive in Cali.\n\n"
            f"{total_fotos or 'These'} standalone photo(s) are now live in one place.\n"
            f"Full album: {album_url}\n\n"
            f"Which one should become the cover?\n\n"
            f"{HASHTAGS}\n\n"
            f"{LINKTREE_URL}"
        )

    fecha_legible = datetime.strptime(fecha, "%Y-%m-%d").strftime("%b %d, %Y")
    return (
        f"New gallery: a night from the performative archive in Cali.\n\n"
        f"Photos from {fecha_legible} are now live.\n"
        f"Full album: {album_url}\n\n"
        f"Which photo should become the cover?\n\n"
        f"{HASHTAGS}\n\n"
        f"{LINKTREE_URL}"
    )


def crear_caption_foto(stem):
    return (
        f"From the performative archive in Cali.\n"
        f"Archive frame: {stem}\n\n"
        f"{HASHTAGS}"
    )


def extraer_stem_caption(caption):
    if not caption:
        return None
    match = re.search(r"Archive frame:\s*(.+)", caption)
    if match:
        return match.group(1).strip()
    return None


def crear_grupos_album(por_fecha):
    grupos = []
    fotos_sueltas = []

    for fecha in sorted(por_fecha):
        fotos = por_fecha[fecha]
        if len(fotos) == 1:
            fotos_sueltas.extend(fotos)
        else:
            grupos.append(
                {
                    "fecha": fecha,
                    "etiqueta": fecha,
                    "nombre_album": f"Fotos {fecha}",
                    "fotos": fotos,
                }
            )

    if fotos_sueltas:
        grupos.insert(
            0,
            {
                "fecha": None,
                "etiqueta": SINGLE_PHOTO_ALBUM_NAME,
                "nombre_album": SINGLE_PHOTO_ALBUM_NAME,
                "fotos": sorted(fotos_sueltas, key=lambda p: p.name),
            },
        )

    return grupos


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
FB_FALLBACK_ALBUM_ID = ENV.get("META_FB_FALLBACK_ALBUM_ID", "")
FB_FALLBACK_ALBUM_NAME = ENV.get("META_FB_FALLBACK_ALBUM_NAME", "")


class MetaAlbumCapabilityError(RuntimeError):
    pass


def resumir_error_meta(error):
    partes = []
    for key in ("message", "type", "code", "error_subcode", "fbtrace_id"):
        value = error.get(key)
        if value is not None:
            partes.append(f"{key}={value}")
    return ", ".join(partes) or str(error)


def es_bloqueo_capability(error):
    mensaje = str(error.get("message", "")).lower()
    return error.get("code") == 3 and "capability" in mensaje


def verificar_scopes_page_token(info):
    scopes = set(info.get("scopes") or [])
    faltantes_requeridos = sorted(REQUIRED_PAGE_SCOPES - scopes)
    faltantes_recomendados = sorted(RECOMMENDED_PAGE_SCOPES - scopes)

    if faltantes_requeridos:
        logging.error("[auth] Faltan permisos requeridos en el Page token: %s",
                      ", ".join(faltantes_requeridos))
        return False

    logging.info("[auth] Permisos requeridos presentes: %s",
                 ", ".join(sorted(REQUIRED_PAGE_SCOPES)))
    if faltantes_recomendados:
        logging.warning("[auth] Permisos recomendados ausentes: %s",
                        ", ".join(faltantes_recomendados))
    return True


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
        return verificar_scopes_page_token(info)

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
            return verificar_scopes_page_token(page_info)

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


def crear_jpeg_seguro(origen):
    from PIL import Image, ImageCms, ImageFile, ImageOps

    ImageFile.LOAD_TRUNCATED_IMAGES = True
    Image.MAX_IMAGE_PIXELS = None

    tmp = tempfile.NamedTemporaryFile(suffix=".jpg", delete=False)
    destino = Path(tmp.name)
    tmp.close()

    try:
        with Image.open(origen) as image:
            image = ImageOps.exif_transpose(image)
            dimensiones_originales = image.size
            icc_profile = image.info.get("icc_profile")
            if icc_profile:
                try:
                    origen_color = ImageCms.ImageCmsProfile(BytesIO(icc_profile))
                    srgb = ImageCms.createProfile("sRGB")
                    image = ImageCms.profileToProfile(image, origen_color, srgb, outputMode="RGB")
                except Exception:
                    image = image.convert("RGB")
            else:
                image = image.convert("RGB")
            resampling = getattr(getattr(Image, "Resampling", Image), "LANCZOS")
            image.thumbnail((MAX_UPLOAD_EDGE, MAX_UPLOAD_EDGE), resampling)
            dimensiones_finales = image.size
            image.save(destino, "JPEG", quality=JPEG_UPLOAD_QUALITY, optimize=True, progressive=True)

        if not destino.exists() or destino.stat().st_size < 1024:
            raise RuntimeError("JPEG seguro invalido")

        logging.info(
            "[prep] %s %sx%s -> JPEG seguro %sx%s %.1f MB",
            origen.name,
            dimensiones_originales[0],
            dimensiones_originales[1],
            dimensiones_finales[0],
            dimensiones_finales[1],
            destino.stat().st_size / 1_000_000,
        )
        return destino
    except Exception:
        if destino.exists():
            os.unlink(destino)
        raise


def preparar_foto_upload(foto):
    temporales = []
    origen = foto

    if foto.suffix.lower() in RAW_EXTS:
        tmp = tempfile.NamedTemporaryFile(suffix=".jpg", delete=False)
        jpeg_temp = Path(tmp.name)
        tmp.close()
        if not convertir_dng_a_jpeg(foto, jpeg_temp):
            if jpeg_temp.exists():
                os.unlink(jpeg_temp)
            return None, temporales
        temporales.append(jpeg_temp)
        origen = jpeg_temp

    try:
        jpeg_seguro = crear_jpeg_seguro(origen)
        temporales.append(jpeg_seguro)
        return jpeg_seguro, temporales
    except Exception as e:
        logging.warning("[prep] No se pudo preparar %s: %s", foto.name, e)
        return None, temporales


def limpiar_temporales(paths):
    for path in paths:
        try:
            if path and path.exists():
                os.unlink(path)
        except OSError:
            pass


def crear_album(nombre):
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
                if es_bloqueo_capability(err):
                    logging.error("[album.capability] Meta bloqueo la creacion de albumes para esta App/Page: %s",
                                  resumir_error_meta(err))
                    logging.error("[album.capability] El token puede leer albumes y subir fotos, pero el App no tiene capability para POST /%s/albums.",
                                  FB_PAGE_ID)
                    logging.error("[album.capability] Soluciones: habilitar/aprobar esa capability en Meta o crear manualmente el album '%s' en Facebook antes de correr.",
                                  nombre)
                    raise MetaAlbumCapabilityError(err.get("message", "Meta album capability missing"))
                if "duplicate" in str(err).lower():
                    albumes = listar_albumes()
                    if nombre in albumes:
                        return albumes[nombre]
                logging.warning("[album] Error (intento %s/3): %s", i + 1, resumir_error_meta(err))
        except Exception as e:
            if isinstance(e, MetaAlbumCapabilityError):
                raise
            logging.warning("[album] Exception (intento %s/3): %s", i + 1, e)
        time.sleep(3 * (i + 1))
    return None


def listar_albumes():
    for intento in range(1, 4):
        albumes = {}
        url = f"{GRAPH_URL}/{FB_PAGE_ID}/albums"
        params = {"access_token": FB_TOKEN, "limit": "100", "fields": "id,name"}
        try:
            while url:
                r = requests.get(url, params=params if "?" not in url else {}, timeout=30)
                data = r.json()
                if "error" in data:
                    raise RuntimeError(resumir_error_meta(data["error"]))
                for a in data.get("data", []):
                    if a.get("name") and a.get("id"):
                        albumes[a["name"]] = a["id"]
                url = data.get("paging", {}).get("next", "")
                params = {}

            if albumes:
                logging.info("[album] Albumes remotos detectados: %s", len(albumes))
                return albumes
            logging.warning("[album] Lectura de albumes vacia (intento %s/3).", intento)
        except Exception as e:
            logging.warning("[album] No se pudieron listar albumes (intento %s/3): %s",
                            intento, e)
        time.sleep(3 * intento)
    return {}


def obtener_info_album(album_id):
    data = graph_get(album_id, {"fields": "id,name,link"})
    if data.get("id") == album_id:
        return data
    if "error" in data:
        logging.error("[album.fallback] No se pudo validar album fallback %s: %s",
                      album_id, resumir_error_meta(data["error"]))
    return {}


def resolver_album_fallback(albumes):
    if FB_FALLBACK_ALBUM_ID:
        info = obtener_info_album(FB_FALLBACK_ALBUM_ID)
        if info:
            return info["id"], info.get("name") or FB_FALLBACK_ALBUM_ID
        return None, None

    if FB_FALLBACK_ALBUM_NAME:
        album_id = albumes.get(FB_FALLBACK_ALBUM_NAME)
        if album_id:
            return album_id, FB_FALLBACK_ALBUM_NAME
        logging.error("[album.fallback] META_FB_FALLBACK_ALBUM_NAME no existe en Facebook: %s",
                      FB_FALLBACK_ALBUM_NAME)

    return None, None


def obtener_album_para_fecha(nombre_album, albumes):
    album_id = albumes.get(nombre_album)
    if album_id:
        logging.info("[album] Ya existe: '%s'", nombre_album)
        return album_id, nombre_album

    albumes_actualizados = listar_albumes()
    albumes.update(albumes_actualizados)
    album_id = albumes.get(nombre_album)
    if album_id:
        logging.info("[album] Ya existe tras refrescar: '%s'", nombre_album)
        return album_id, nombre_album

    try:
        album_id = crear_album(nombre_album)
    except MetaAlbumCapabilityError:
        fallback_id, fallback_nombre = resolver_album_fallback(albumes)
        if fallback_id:
            logging.warning("[album.fallback] Usando album existente '%s' para la fecha '%s' porque Meta no permite crear albumes por API.",
                            fallback_nombre, nombre_album)
            return fallback_id, fallback_nombre
        raise

    if album_id:
        albumes[nombre_album] = album_id
        return album_id, nombre_album

    return None, None


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


def listar_fotos_album_por_stem(album_id):
    existentes = {}
    url = f"{GRAPH_URL}/{album_id}/photos"
    params = {"access_token": FB_TOKEN, "limit": "100", "fields": "id,name,album"}
    while url:
        try:
            r = requests.get(url, params=params if "?" not in url else {}, timeout=30)
            data = r.json()
        except requests.RequestException as e:
            logging.warning("[recover] No se pudieron listar fotos existentes en %s: %s",
                            album_id, e.__class__.__name__)
            return existentes

        if "error" in data:
            logging.warning("[recover] Error listando fotos existentes en %s: %s",
                            album_id, resumir_error_meta(data["error"]))
            return existentes

        for item in data.get("data", []):
            stem = extraer_stem_caption(item.get("name"))
            if stem and item.get("id"):
                existentes[stem] = item["id"]

        url = data.get("paging", {}).get("next")
        params = {}

    if existentes:
        logging.info("[recover] Fotos ya presentes en album %s: %s", album_id, len(existentes))
    return existentes


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
    data = graph_get(post_id, {"fields": "id,is_published,created_time,permalink_url,link"})
    if data.get("id") != post_id:
        if buscar_post_publicado(post_id):
            logging.info("[confirm] Teaser confirmado via published_posts: %s", post_id)
            return True
        logging.warning("[confirm] Teaser no accesible todavia: %s", post_id)
        return False
    if "is_published" in data and data.get("is_published") is not True:
        logging.warning("[confirm] Teaser existe pero no figura publicado todavia: %s", post_id)
        return False
    return True


def buscar_post_publicado(post_id):
    if not post_id:
        return False
    data = graph_get(
        f"{FB_PAGE_ID}/published_posts",
        {"fields": "id,created_time,permalink_url", "limit": "50"},
    )
    for item in data.get("data", []):
        if item.get("id") == post_id:
            return True
    return False


def buscar_teaser_existente(album_url):
    data = graph_get(
        f"{FB_PAGE_ID}/published_posts",
        {"fields": "id,message,created_time,permalink_url", "limit": "50"},
    )
    for item in data.get("data", []):
        if album_url in (item.get("message") or ""):
            logging.info("[teaser] Teaser existente detectado (id=%s)", item.get("id"))
            return item.get("id")
    return None


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


def subir_foto_a_album(album_id, foto_path, mensaje, nombre_archivo=None):
    nombre_remoto = nombre_archivo or foto_path.name
    logging.info("[album.foto] Subiendo %s ...", nombre_remoto)
    url = f"{GRAPH_URL}/{album_id}/photos"
    for i in range(3):
        try:
            with open(foto_path, "rb") as f:
                files = {"source": (nombre_remoto, f, "image/jpeg")}
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


def subir_foto_temp(foto_path, nombre_archivo=None):
    nombre_remoto = nombre_archivo or foto_path.name
    url = f"{GRAPH_URL}/{FB_PAGE_ID}/photos"
    for i in range(3):
        try:
            with open(foto_path, "rb") as f:
                files = {"source": (nombre_remoto, f, "image/jpeg")}
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


def publicar_teaser_foto_directa(foto_path, mensaje, nombre_archivo=None):
    nombre_remoto = nombre_archivo or foto_path.name
    url = f"{GRAPH_URL}/{FB_PAGE_ID}/photos"
    for i in range(3):
        try:
            with open(foto_path, "rb") as f:
                files = {"source": (nombre_remoto, f, "image/jpeg")}
                data = {"message": mensaje, "published": "true", "access_token": FB_TOKEN}
                r = requests.post(url, files=files, data=data, timeout=120)
                resp = r.json()
                if "post_id" in resp:
                    logging.info("[teaser] Foto-teaser publicada inmediatamente (post_id=%s)", resp["post_id"])
                    return resp["post_id"]
                if "id" in resp:
                    logging.info("[teaser] Foto-teaser publicada inmediatamente (photo_id=%s)", resp["id"])
                    return resp["id"]
                if "error" in resp:
                    logging.warning("[teaser] Foto directa error (intento %s/3): %s",
                                    i + 1, resp["error"].get("message"))
        except Exception as e:
            logging.warning("[teaser] Foto directa exception (intento %s/3): %s", i + 1, e)
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

    for grupo in crear_grupos_album(por_fecha):
        fecha = grupo["fecha"]
        etiqueta = grupo["etiqueta"]
        nombre_album = grupo["nombre_album"]
        fotos = grupo["fotos"]

        try:
            album_id, nombre_album_remoto = obtener_album_para_fecha(nombre_album, albumes)
        except MetaAlbumCapabilityError:
            logging.error("[stop] Se detiene la corrida: sin capability para crear albumes y sin fallback configurado.")
            logging.error("[stop] Si creas manualmente '%s' en Facebook, vuelve a correr y el script lo detectara.", nombre_album)
            return

        if not album_id:
            logging.error("[album] No se pudo obtener album para %s; se salta este grupo.", etiqueta)
            continue

        logging.info("[grupo] %s: %s foto(s)", etiqueta, len(fotos))

        foto_paths_subidas = []
        foto_ids_subidas = []
        inicio_album = time.monotonic()
        total_fotos_album = len(fotos)
        fotos_existentes = listar_fotos_album_por_stem(album_id)

        for indice, foto in enumerate(fotos, start=1):
            if foto.stem in fotos_existentes:
                fb_id = fotos_existentes[foto.stem]
                foto_paths_subidas.append(foto)
                foto_ids_subidas.append(fb_id)
                logging.info("[skip] %s ya estaba subida al album (id=%s)", foto.name, fb_id)
                registrar_progreso_album(etiqueta, indice, total_fotos_album, inicio_album)
                continue

            foto_a_subir, temporales = preparar_foto_upload(foto)
            if not foto_a_subir:
                limpiar_temporales(temporales)
                registrar_progreso_album(etiqueta, indice, total_fotos_album, inicio_album)
                continue
            mensaje = crear_caption_foto(foto.stem)
            fb_id = subir_foto_a_album(album_id, foto_a_subir, mensaje, nombre_archivo=foto.name)
            limpiar_temporales(temporales)

            if fb_id:
                foto_paths_subidas.append(foto)
                foto_ids_subidas.append(fb_id)
                logging.info("[ok] %s subida al album (id=%s)", foto.name, fb_id)
            else:
                logging.error("[fail] No se pudo subir %s", foto.name)

            registrar_progreso_album(etiqueta, indice, total_fotos_album, inicio_album)
            time.sleep(2)

        if not foto_paths_subidas:
            continue

        # Publicar teaser inmediato cuando el album ya termino de subirse.
        album_url = f"https://www.facebook.com/media/set/?set=a.{album_id}"
        teaser_paths = seleccionar_fotos_teaser(foto_paths_subidas, TEASER_COUNT)
        total = len(foto_paths_subidas)

        mensaje_teaser = crear_caption_teaser(fecha, album_url, nombre_album=nombre_album_remoto, total_fotos=total)
        teaser_post_id = buscar_teaser_existente(album_url)
        teaser_temp_ids = []
        if teaser_post_id:
            logging.info("[teaser] No se publica duplicado para %s.", nombre_album_remoto)
        elif len(teaser_paths) == 1:
            teaser_path, temporales = preparar_foto_upload(teaser_paths[0])
            if teaser_path:
                teaser_post_id = publicar_teaser_foto_directa(
                    teaser_path,
                    mensaje_teaser,
                    nombre_archivo=teaser_paths[0].name,
                )
            limpiar_temporales(temporales)
        else:
            # Subir como no-publicadas para el carrusel
            for fp in teaser_paths[:TEASER_COUNT]:
                teaser_path, temporales = preparar_foto_upload(fp)
                if teaser_path:
                    tid = subir_foto_temp(teaser_path, nombre_archivo=fp.name)
                    limpiar_temporales(temporales)
                else:
                    limpiar_temporales(temporales)
                    tid = None
                if tid:
                    teaser_temp_ids.append(tid)
                time.sleep(2)

        if len(teaser_temp_ids) >= 2:
            teaser_post_id = publicar_post_carrusel(teaser_temp_ids, mensaje_teaser)
        elif len(teaser_temp_ids) == 1 and total < TEASER_COUNT:
            teaser_path, temporales = preparar_foto_upload(teaser_paths[0])
            if teaser_path:
                teaser_post_id = publicar_teaser_foto_directa(
                    teaser_path,
                    mensaje_teaser,
                    nombre_archivo=teaser_paths[0].name,
                )
            limpiar_temporales(temporales)

        if not confirmar_album_publicado(album_id, nombre_album_remoto, foto_ids_subidas, teaser_post_id):
            logging.error("[archive] No se mueven fotos locales de %s hasta confirmar Facebook.", nombre_album)
            continue

        # Crear carpeta local con el nombre del album y copiar fotos
        album_dir = DIR_PROCESADAS / nombre_album
        album_dir.mkdir(parents=True, exist_ok=True)
        for foto in foto_paths_subidas:
            if not foto.exists():
                logging.warning("[archive] Omitiendo copia de %s porque el archivo original ya no existe localmente.", foto.name)
                continue
            destino = album_dir / foto.name
            shutil.copy2(str(foto), str(destino))
            logging.info("[archive] %s -> %s", foto.name, destino)

        # Mover originales a carpeta plana (legacy)
        for foto in foto_paths_subidas:
            if not foto.exists():
                continue
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
                     etiqueta, total, len(teaser_paths[:TEASER_COUNT]) if teaser_post_id else 0)

    total_f = sum(len(por_fecha[f]) for f in por_fecha)
    logging.info("=== COMPLETADO: %s foto(s) en %s fecha(s) ===", total_f, len(por_fecha))


def main():
    print("=" * 60)
    print("  FACEBOOK - ALBUM DIARIO + TEASER INMEDIATO")
    print("=" * 60)
    print(f"  Linktree : {LINKTREE_URL}")
    print(f"  Teaser   : {TEASER_COUNT} fotos")
    print("=" * 60)
    procesar()


if __name__ == "__main__":
    main()
