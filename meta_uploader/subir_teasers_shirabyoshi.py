"""
subir_teasers_shirabyoshi.py
Evacua UN SOLO TEASER a la vez, con lógica anti-spam y evasión Code 368.
- Maneja archivo de backoff (.bloqueo_368) para obligar pausa de 24h.
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

SOURCE_DIR = ROOT / "videos subidos exitosamente"
DONE_DIR   = ROOT / "subidos a facebbok"
FAILED_DIR = ROOT / "fallidos_facebook"
LOG_FILE   = BASE_DIR / "fb_shirabyoshi_teasers.log"
BACKOFF_FILE = BASE_DIR / ".bloqueo_368"

TEASER_RE      = re.compile(r"(?i)_teaser_\d+")
SUPPORTED_EXTS = {".mp4", ".mov", ".mkv"}
REEL_ASPECT_TOLERANCE = 0.08

# --- Credenciales ---
FB_PAGE_ID_TEASER = os.environ.get("META_FB_PAGE_ID_TEASER", "1347014641828725")
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


def check_backoff() -> bool:
    """Verifica si estamos en período de castigo de 24 horas por Code 368."""
    if not BACKOFF_FILE.exists():
        return False
    try:
        mtime = datetime.fromtimestamp(BACKOFF_FILE.stat().st_mtime)
        cooldown_end = mtime + timedelta(hours=24)
        if datetime.now() < cooldown_end:
            logging.warning(
                "BACKOFF ACTIVO: La página está bloqueada temporalmente (Code 368). "
                f"El castigo termina el {cooldown_end.strftime('%Y-%m-%d %H:%M:%S')}."
            )
            return True
        else:
            logging.info("El período de backoff (24h) ha terminado. Levantando restricción.")
            BACKOFF_FILE.unlink()
            return False
    except Exception as e:
        logging.error(f"Error comprobando archivo de backoff: {e}")
        return False


def set_backoff():
    """Marca el inicio de un castigo de 24 horas."""
    BACKOFF_FILE.touch()
    logging.error("Se ha creado el archivo .bloqueo_368. Se detienen las subidas por 24h para proteger la cuenta.")


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
    """Genera texto dinámico y hashtags variables para evadir filtros de similitud."""
    stem = video_path.stem
    
    # Pool de hashtags para variar
    pool = [
        "#teatro", "#performance", "#escriturasperformaticas", 
        "#artecontemporaneo", "#shirabyoshi", "#cultura", 
        "#teatrocolombiano", "#artesescenicas", "#teatroindependiente"
    ]
    # Seleccionamos entre 3 y 5 hashtags aleatorios para que cada post sea único
    selected_tags = random.sample(pool, random.randint(3, 5))
    tags_str = " ".join(selected_tags)
    
    # Variar el espaciado también ayuda
    spaces = "\n" * random.randint(1, 3)
    
    return (
        f"#PW | {stem}{spaces}"
        "Síguenos también en Instagram linktr.ee/performaticwritingscali\n\n"
        f"{tags_str}"
    )


def move_to_done(video_path: Path) -> None:
    DONE_DIR.mkdir(parents=True, exist_ok=True)
    dest = DONE_DIR / video_path.name
    if dest.exists():
        video_path.unlink()
    else:
        shutil.move(str(video_path), str(dest))


def upload_video(video_path: Path) -> bool:
    caption = build_caption(video_path)
    page_id = FB_PAGE_ID_TEASER
    page_token = FB_PAGE_TOKEN_TEASER
    page_name = "Shirabyoshi Writings (Teasers)"

    if not page_id or not page_token:
        logging.error("Faltan credenciales para la página %s", page_name)
        return False

    if is_reel_safe(video_path):
        logging.info("Subiendo TEASER como REEL (9:16) a %s: %s", page_name, video_path.name)
        try:
            result = upload_fb_reel(str(video_path), caption, page_id=page_id, page_token=page_token)
            if result:
                logging.info("Subida exitosa como REEL | video_id=%s", result)
                return True
            logging.warning("REEL falló (resultado vacío), probando VIDEO ESTÁNDAR como fallback...")
        except MetaRateLimitError as exc:
            logging.warning(
                "Code 368 en REEL endpoint — probando VIDEO ESTÁNDAR como fallback antibloqueo. (%s)", exc
            )

    logging.info("Subiendo TEASER como VIDEO ESTANDAR a %s: %s", page_name, video_path.name)
    try:
        result = upload_fb_video_standard(str(video_path), caption, page_id=page_id, page_token=page_token)
    except MetaRateLimitError as exc:
        logging.error(
            "Code 368 también en VIDEO ESTANDAR. La página está bloqueada."
        )
        set_backoff()
        return False

    if result:
        logging.info("Subida exitosa | video_id=%s", result)
        return True
    else:
        logging.error("Fallo la subida.")
        return False


def main():
    logging.info("=" * 60)
    logging.info("  NUEVO EVACUADOR SHIRABYOSHI TEASERS (ANTI-SPAM)")
    logging.info("=" * 60)

    if check_backoff():
        # Retornamos 2 para que el bash script no lo cuente como un "fallo" del ciclo 
        # sino como un "nada que hacer, esperando".
        sys.exit(2)

    if not SOURCE_DIR.exists():
        sys.exit(1)

    videos = sorted(
        f for f in SOURCE_DIR.iterdir()
        if f.is_file()
        and f.suffix.lower() in SUPPORTED_EXTS
        and not f.name.endswith(".part")
        and TEASER_RE.search(f.stem)
    )

    if not videos:
        logging.info("No hay TEASERS pendientes. Nada que hacer.")
        sys.exit(2)

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
        sys.exit(1)


if __name__ == "__main__":
    main()
