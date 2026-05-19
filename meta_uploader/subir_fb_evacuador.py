"""
subir_fb_evacuador.py
Evacuador de Facebook: Lee videos de 'videos subidos exitosamente',
los sube a Facebook como reels (si son teasers) o videos normales (si son crudos),
y los mueve a 'subidos a facebbok' al finalizar con exito.
"""
import json
import logging
import os
import re
import shutil
import sys
from pathlib import Path

# Asegurar que Python encuentre meta_uploader en el mismo directorio
BASE_DIR = Path(__file__).resolve().parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from meta_uploader import (
    upload_fb_reel,
    upload_fb_video_standard,
)

# --- Rutas ---
# Detectar si estamos en Termux (Android) o en PC
TERMUX_PREFIX = os.environ.get("PREFIX", "")
IS_TERMUX = "com.termux" in TERMUX_PREFIX

if IS_TERMUX:
    ROOT = Path("/sdcard/Antigravity")
else:
    # Rutas del PC (Linux Parrot)
    ROOT = Path("/home/zerausn/Documents/Antigravity")

SOURCE_DIR = ROOT / "videos subidos exitosamente"
DONE_DIR = ROOT / "subidos a facebbok"
LOG_FILE = BASE_DIR / "fb_evacuador.log"

TEASER_RE = re.compile(r"(?i)_teaser_\d+")
SUPPORTED_EXTS = {".mp4", ".mov", ".mkv"}

# --- Logging ---
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - [FB-EVACUA] - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE, encoding="utf-8"),
        logging.StreamHandler(),
    ],
)


def build_caption(video_path: Path) -> str:
    stem = video_path.stem
    return f"#PW | {stem}\n\nSíguenos también en Instagram linktr.ee/performaticwritingscali\n\n#teatro #performance #escriturasperformaticas"


def move_to_done(video_path: Path) -> None:
    DONE_DIR.mkdir(parents=True, exist_ok=True)
    dest = DONE_DIR / video_path.name
    if dest.exists():
        logging.info("Ya existe en destino, borrando origen: %s", video_path.name)
        video_path.unlink()
    else:
        shutil.move(str(video_path), str(dest))
        logging.info("Movido a 'subidos a facebbok': %s", video_path.name)


def upload_video(video_path: Path) -> bool:
    caption = build_caption(video_path)
    is_teaser = bool(TEASER_RE.search(video_path.stem))

    if is_teaser:
        logging.info("Subiendo como REEL de Facebook: %s", video_path.name)
        result = upload_fb_reel(str(video_path), caption)
    else:
        logging.info("Subiendo como VIDEO ESTANDAR de Facebook: %s", video_path.name)
        result = upload_fb_video_standard(str(video_path), caption)

    if result:
        logging.info("Subida exitosa | video_id=%s | archivo=%s", result, video_path.name)
        return True
    else:
        logging.error("Fallo la subida de: %s", video_path.name)
        return False


def main():
    logging.info("=" * 60)
    logging.info("  FB EVACUADOR - Leyendo carpeta: %s", SOURCE_DIR)
    logging.info("=" * 60)

    if not SOURCE_DIR.exists():
        logging.error("La carpeta fuente no existe: %s", SOURCE_DIR)
        return

    videos = sorted(
        f for f in SOURCE_DIR.iterdir()
        if f.is_file() and f.suffix.lower() in SUPPORTED_EXTS and not f.name.endswith('.part')
    )

    if not videos:
        logging.info("No hay videos pendientes en 'videos subidos exitosamente'. Nada que hacer.")
        return

    logging.info("Encontrados %s video(s) para evacuar a Facebook.", len(videos))

    exitos = 0
    fallos = 0
    for video in videos:
        try:
            # Evitar procesar archivos parciales en curso (.part)
            if video.name.endswith('.part'):
                logging.info('Saltando archivo parcial: %s', video.name)
                continue

            # Esperar brevemente a que el archivo deje de crecer (estabilidad)
            stable = False
            last_size = video.stat().st_size
            for _ in range(3):
                time.sleep(1)
                try:
                    sz = video.stat().st_size
                except Exception:
                    sz = last_size
                if sz == last_size:
                    stable = True
                    break
                last_size = sz
            if not stable:
                logging.info('Archivo en cambio activo, saltando por ahora: %s', video.name)
                continue
            ok = upload_video(video)
            if ok:
                move_to_done(video)
                exitos += 1
            else:
                fallos += 1
        except Exception as e:
            logging.error("Error inesperado procesando %s: %s", video.name, e)
            fallos += 1

    logging.info("=" * 60)
    logging.info("  Evacuacion completada. Exitos: %s | Fallos: %s", exitos, fallos)
    logging.info("=" * 60)


if __name__ == "__main__":
    main()
