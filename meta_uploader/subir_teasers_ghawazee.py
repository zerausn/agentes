"""
subir_teasers_ghawazee.py
Evacua UN SOLO TEASER a la vez a Ghawazee Writings, con lógica anti-spam y evasión Code 368.
- Maneja archivo de backoff (.bloqueo_368_ghawazee) para obligar pausa de 24h.
- Genera variaciones dinámicas de texto (hashtags) para evadir filtros de similitud.
- Intenta REEL, si falla con 368 intenta VIDEO NORMAL, si ambos fallan activa backoff.
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
from datetime import datetime, timedelta
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
ROOT = Path(os.environ.get("AGENTES_STORAGE_ROOT", ""))
if not str(ROOT):
    mobile_root = Path("/sdcard/Antigravity")
    if mobile_root.exists():
        ROOT = mobile_root
    else:
        ROOT = Path("/home/zerausn/Documents/Antigravity")

SOURCE_DIR   = ROOT / "teasers_pendientes"
DONE_DIR     = ROOT / "subidos a facebbok"
FAILED_DIR   = ROOT / "fallidos_facebook"
LOG_FILE     = BASE_DIR / "fb_ghawazee_teasers.log"
BACKOFF_FILE = BASE_DIR / ".bloqueo_368_ghawazee"

TEASER_RE      = re.compile(r"(?i)_teaser_\d+")
SUPPORTED_EXTS = {".mp4", ".mov", ".mkv"}
REEL_ASPECT_TOLERANCE = 0.08

# --- Credenciales ---
FB_PAGE_ID_GHAWAZEE = os.environ.get("META_FB_PAGE_ID_GHAWAZEE", "1288381367700799")
FB_PAGE_TOKEN_GHAWAZEE = os.environ.get("META_FB_PAGE_TOKEN_GHAWAZEE", "")

# --- Logging ---
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE, encoding="utf-8"),
        logging.StreamHandler(),
    ],
)


def check_backoff() -> bool:
    """Verifica si estamos en periodo de castigo de 24 horas por Code 368."""
    if not BACKOFF_FILE.exists():
        return False
    try:
        mtime = datetime.fromtimestamp(BACKOFF_FILE.stat().st_mtime)
        cooldown_end = mtime + timedelta(hours=24)
        if datetime.now() < cooldown_end:
            logging.warning(
                "BACKOFF ACTIVO: La página está bloqueada temporalmente (Code 368). "
                "El castigo termina el %s.", cooldown_end.strftime("%Y-%m-%d %H:%M:%S")
            )
            return True
        else:
            logging.info("El período de backoff (24h) ha terminado. Levantando restricción.")
            BACKOFF_FILE.unlink()
            return False
    except Exception as e:
        logging.error("Error comprobando archivo de backoff: %s", e)
        return False


def set_backoff():
    """Marca el inicio de un castigo de 24 horas."""
    BACKOFF_FILE.touch()
    logging.error(
        "Se ha creado el archivo .bloqueo_368_ghawazee. "
        "Se detienen las subidas por 24h para proteger la cuenta."
    )


def probe_video_dimensions(video_path: Path):
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
    width, height = probe_video_dimensions(video_path)
    if not width or not height or height <= width:
        return False
    ratio = width / height
    return abs(ratio - (9 / 16)) <= REEL_ASPECT_TOLERANCE


def build_caption(video_path: Path) -> str:
    """Genera texto dinamico y hashtags variables para evadir filtros de similitud.
    Prefijo: #GW (Ghawazee Writings). Frases artisticas al final."""
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
    tags_str = "#ghawazee " + " ".join(two_random)

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
        f"#GW | {stem}\n\n"
        "linktr.ee/performaticwritingscali\n\n"
        f"{tags_str}\n\n"
        f"{frase}"
    )


def move_to_done(video_path: Path) -> None:
    DONE_DIR.mkdir(parents=True, exist_ok=True)
    dest = DONE_DIR / video_path.name
    if dest.exists():
        video_path.unlink()
    else:
        shutil.move(str(video_path), str(dest))


def move_to_failed(video_path: Path) -> None:
    FAILED_DIR.mkdir(parents=True, exist_ok=True)
    dest = FAILED_DIR / video_path.name
    if dest.exists():
        video_path.unlink()
    else:
        shutil.move(str(video_path), str(dest))


def upload_video(video_path: Path) -> bool:
    caption = build_caption(video_path)
    page_id = FB_PAGE_ID_GHAWAZEE
    page_token = FB_PAGE_TOKEN_GHAWAZEE
    page_name = "Ghawazee Writings"

    if not page_id or not page_token:
        logging.error("Faltan credenciales para la página %s", page_name)
        return False

    os.environ["FB_PAGE_ID"] = page_id
    os.environ["FB_PAGE_TOKEN"] = page_token

    if is_reel_safe(video_path):
        logging.info("Subiendo TEASER como REEL (9:16) a %s: %s", page_name, video_path.name)
        try:
            result = upload_fb_reel(str(video_path), caption)
            if result:
                logging.info("Subida exitosa como REEL | video_id=%s", result)
                return True
            logging.warning("REEL falló (resultado vacío o permiso denegado), probando VIDEO ESTÁNDAR...")
        except MetaRateLimitError as exc:
            logging.warning(
                "Code 368 en REEL endpoint — probando VIDEO ESTÁNDAR como fallback antibloqueo. (%s)", exc
            )

    logging.info("Subiendo TEASER como VIDEO ESTÁNDAR a %s: %s", page_name, video_path.name)
    try:
        result = upload_fb_video_standard(str(video_path), caption)
    except MetaRateLimitError as exc:
        logging.error("Code 368 también en VIDEO ESTÁNDAR. Página bloqueada temporalmente.")
        set_backoff()
        return False

    if result:
        logging.info("Subida exitosa | video_id=%s", result)
        return True
    else:
        logging.error("Falló la subida de: %s", video_path.name)
        return False


def main():
    logging.info("=" * 60)
    logging.info("  NUEVO EVACUADOR GHAWAZEE TEASERS (ANTI-SPAM) - 30/dia")
    logging.info("  Carpeta fuente: %s", SOURCE_DIR)
    logging.info("=" * 60)

    if check_backoff():
        sys.exit(2)

    if not SOURCE_DIR.exists():
        logging.error("La carpeta fuente no existe: %s", SOURCE_DIR)
        sys.exit(1)

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
        sys.exit(0)
    else:
        move_to_failed(video)
        sys.exit(1)


if __name__ == "__main__":
    main()
