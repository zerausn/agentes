"""
subir_fb_evacuador_teasers.py  (VERSION BASH-LOOP — sin time.sleep interno)
Evacua UN SOLO TEASER de 'teasers_pendientes' a Facebook y retorna.
El loop/pausa lo gestiona el script bash (con termux-wake-lock).

SOLO TEASERS -> Shirabyoshi Writings (ID: 1347014641828725)

Exit codes:
  0  -- video subido y movido OK
  2  -- no habia videos pendientes (carpeta vacía)
  1  -- error durante la subida
"""
import json
import logging
import os
import random
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from meta_uploader import (
    upload_fb_reel,
    upload_fb_video_standard,
    MetaRateLimitError,
)

# --- Rutas ---
_root_env = os.environ.get("AGENTES_STORAGE_ROOT", "").strip()
if not _root_env:
    mobile_root = Path("/sdcard/Antigravity")
    if mobile_root.exists():
        ROOT = mobile_root
    else:
        ROOT = Path("/home/zerausn/Documents/Antigravity")
else:
    ROOT = Path(_root_env)
if False:
    mobile_root = Path("/sdcard/Antigravity")
    if mobile_root.exists():
        ROOT = mobile_root
    else:
        ROOT = Path("/home/zerausn/Documents/Antigravity")

# CORREGIDO: leer de teasers_pendientes (antes buscaba en "videos subidos exitosamente" que estaba vacía)
SOURCE_DIR = ROOT / "teasers_pendientes"
DONE_DIR   = ROOT / "subidos a facebbok"
FAILED_DIR = ROOT / "fallidos_facebook"
LOG_FILE   = BASE_DIR / "fb_evacuador_teasers.log"

TEASER_RE      = re.compile(r"(?i)_teaser_\d+")
SUPPORTED_EXTS = {".mp4", ".mov", ".mkv"}

# Margen de tolerancia al comparar con la relacion 9:16 exacta
REEL_ASPECT_TOLERANCE = 0.08

# --- IDs de páginas de Facebook ---
FB_PAGE_ID_TEASER = os.environ.get("META_FB_PAGE_ID_TEASER", "1347014641828725")  # Shirabyoshi Writings
FB_PAGE_TOKEN_TEASER = os.environ.get("META_FB_PAGE_TOKEN_TEASER", os.environ.get("META_FB_PAGE_TOKEN", ""))

# --- Logging ---
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE, encoding="utf-8"),
        logging.StreamHandler(),
    ],
)


def probe_video_dimensions(video_path: Path):
    """Usa ffprobe para obtener width y height del primer stream de video."""
    try:
        result = subprocess.run(
            [
                "ffprobe", "-v", "error",
                "-select_streams", "v:0",
                "-show_entries", "stream=width,height",
                "-of", "json",
                str(video_path),
            ],
            capture_output=True, text=True, timeout=30,
        )
        data = json.loads(result.stdout)
        streams = data.get("streams", [])
        if not streams:
            return None, None
        stream = streams[0]
        return int(stream.get("width", 0)), int(stream.get("height", 0))
    except Exception as exc:
        logging.warning("No se pudo inspeccionar dimensiones de %s: %s", video_path.name, exc)
        return None, None


def is_reel_safe(video_path: Path) -> bool:
    """
    Devuelve True si el video es vertical con relacion de aspecto ~9:16.
    Si ffprobe falla, asume que NO es reel-safe (fallback a POST estandar).
    """
    width, height = probe_video_dimensions(video_path)
    if not width or not height or height <= width:
        return False
    ratio = width / height
    return abs(ratio - (9 / 16)) <= REEL_ASPECT_TOLERANCE


def build_caption(video_path: Path) -> str:
    """Genera texto dinamico y hashtags variables para evadir filtros de similitud.
    Prefijo: #PW (Performatic Writings). Frases artisticas al final."""
    stem = video_path.stem

    # Hashtags: siempre 3 en total.
    # 1 fijo = nombre de la pagina, 2 elegidos al azar del pool.
    # (Facebook penaliza el exceso de hashtags desde 2024-2025)
    hashtag_pool = [
        "#teatro", "#performance", "#escriturasperformaticas",
        "#arteescenico", "#arteperformativo",
        "#artesescenicas", "#teatroindependiente", "#arteescena",
        "#performatividad", "#escrituraviva", "#escena",
    ]
    two_random = random.sample(hashtag_pool, 2)
    tags_str = "#performatic " + " ".join(two_random)

    # 24 frases artisticas — se elige una al azar y va AL FINAL
    frases = [
        "Nueva entrega de performance...",
        "Arte y escritura en escena...",
        "Del cuerpo a la palabra...",
        "Escrituras que se mueven...",
        "El cuerpo como territorio...",
        "La voz que toma forma...",
        "Cuando el arte habla sin palabras...",
        "Donde la escritura se hace carne...",
        "El espacio como lienzo vivo...",
        "Lenguaje que desborda la pagina...",
        "El gesto que narra lo inefable...",
        "Cuerpo, texto, presencia...",
        "La escena como laboratorio...",
        "Escrituras que resisten...",
        "El arte que no se detiene...",
        "Desde los margenes de la representacion...",
        "El presente como materia prima...",
        "Donde comienza el acto...",
        "La escritura en su forma mas viva...",
        "Mas alla del texto...",
        "Cuando el cuerpo es el mensaje...",
        "El performance como pregunta...",
        "Arte que toca lo que no se dice...",
        "La escena habla por si sola...",
    ]
    frase = random.choice(frases)

    return (
        f"#PW | {stem}\n\n"
        "linktr.ee/performaticwritingscali\n\n"
        f"{tags_str}\n\n"
        f"{frase}"
    )


def move_to_done(video_path: Path) -> None:
    DONE_DIR.mkdir(parents=True, exist_ok=True)
    dest = DONE_DIR / video_path.name
    if dest.exists():
        logging.info("Ya existe en destino, borrando origen: %s", video_path.name)
        video_path.unlink()
    else:
        shutil.move(str(video_path), str(dest))
        logging.info("Movido a 'subidos a facebbok': %s", video_path.name)


def move_to_failed(video_path: Path) -> None:
    FAILED_DIR.mkdir(parents=True, exist_ok=True)
    dest = FAILED_DIR / video_path.name
    if dest.exists():
        logging.info("Ya existe en fallidos, borrando origen: %s", video_path.name)
        video_path.unlink()
    else:
        shutil.move(str(video_path), str(dest))
        logging.info("Movido a 'fallidos_facebook': %s", video_path.name)


def upload_video(video_path: Path) -> bool:
    caption = build_caption(video_path)
    page_id = FB_PAGE_ID_TEASER
    page_token = FB_PAGE_TOKEN_TEASER
    page_name = "Shirabyoshi Writings (Teasers)"

    if not page_id or not page_token:
        logging.error("Faltan credenciales para la pagina %s (page_id=%s, token=%s)",
                      page_name, page_id, "OK" if page_token else "FALTANTE")
        return False

    # TEASERS son 9:16 -> intentar REEL primero, fallback a VIDEO ESTANDAR
    if is_reel_safe(video_path):
        logging.info("Subiendo TEASER como REEL (9:16) a %s: %s", page_name, video_path.name)
        try:
            result = upload_fb_reel(str(video_path), caption, page_id=page_id, page_token=page_token)
            if result:
                logging.info("Subida exitosa como REEL | video_id=%s | archivo=%s | pagina=%s",
                             result, video_path.name, page_name)
                return True
            logging.warning("REEL fallo (resultado vacio o permiso denegado). Probando VIDEO ESTANDAR...")
        except MetaRateLimitError as exc:
            logging.warning(
                "Code 368 en REEL endpoint — probando VIDEO ESTANDAR como fallback antibloqueo. (%s)", exc
            )

    logging.info("Subiendo TEASER como VIDEO ESTANDAR a %s: %s", page_name, video_path.name)
    try:
        result = upload_fb_video_standard(str(video_path), caption, page_id=page_id, page_token=page_token)
    except MetaRateLimitError as exc:
        logging.error(
            "Code 368 tambien en VIDEO ESTANDAR. Pagina bloqueada temporalmente — esperando al proximo ciclo. (%s)", exc
        )
        return False

    if result:
        logging.info("Subida exitosa | video_id=%s | archivo=%s | pagina=%s",
                     result, video_path.name, page_name)
        return True
    else:
        logging.error("Fallo la subida de: %s a pagina %s", video_path.name, page_name)
        return False


def main():
    logging.info("=" * 60)
    logging.info("  FB EVACUADOR TEASERS (1 video/ciclo) — carpeta: %s", SOURCE_DIR)
    logging.info("  Teasers -> Shirabyoshi Writings (1347014641828725)")
    logging.info("=" * 60)

    if not SOURCE_DIR.exists():
        logging.error("La carpeta fuente no existe: %s", SOURCE_DIR)
        sys.exit(1)

    # Solo videos CON _teaser_ en el nombre
    videos = sorted(
        f for f in SOURCE_DIR.iterdir()
        if f.is_file()
        and f.suffix.lower() in SUPPORTED_EXTS
        and not f.name.endswith(".part")
        and TEASER_RE.search(f.stem)
    )

    if not videos:
        logging.info("No hay TEASERS pendientes en %s. Nada que hacer.", SOURCE_DIR)
        sys.exit(2)

    logging.info("Pendientes TEASERS: %s video(s). Procesando el primero.", len(videos))

    video = videos[0]

    # Verificar estabilidad del archivo (no se este copiando)
    last_size = video.stat().st_size
    for _ in range(3):
        time.sleep(1)
        try:
            sz = video.stat().st_size
        except Exception:
            sz = last_size
        if sz == last_size:
            break
        last_size = sz
    else:
        logging.info("Archivo en cambio activo, saltando: %s", video.name)
        sys.exit(2)

    ok = upload_video(video)
    if ok:
        move_to_done(video)
        logging.info("CICLO OK — bash hara pausa antes del proximo.")
        sys.exit(0)
    else:
        move_to_failed(video)
        logging.error("CICLO FALLO — video movido a fallidos_facebook para no bloquear la cola.")
        sys.exit(1)


if __name__ == "__main__":
    main()
