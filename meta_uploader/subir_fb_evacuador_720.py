"""
subir_fb_evacuador_720.py  (VERSION BASH-LOOP — sin time.sleep interno)
Evacua UN SOLO VIDEO de 'videos subidos exitosamente' a Facebook y retorna.
El loop/pausa de 720s lo gestiona el script bash (con termux-wake-lock).
Exit codes:
  0  — video subido y movido OK
  2  — no habia videos pendientes (carpeta vacía)
  1  — error durante la subida
"""
import json
import logging
import os
import re
import shutil
import sys
import time
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from meta_uploader import (
    upload_fb_reel,
    upload_fb_video_standard,
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
LOG_FILE   = BASE_DIR / "fb_evacuador.log"

TEASER_RE     = re.compile(r"(?i)_teaser_\d+")
SUPPORTED_EXTS = {".mp4", ".mov", ".mkv"}

# --- Logging ---
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE, encoding="utf-8"),
        logging.StreamHandler(),
    ],
)


def build_caption(video_path: Path) -> str:
    stem = video_path.stem
    return (
        f"#PW | {stem}\n\n"
        "Síguenos también en Instagram linktr.ee/performaticwritingscali\n\n"
        "#teatro #performance #escriturasperformaticas"
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


def upload_video(video_path: Path) -> bool:
    caption  = build_caption(video_path)
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
    logging.info("  FB EVACUADOR (1 video/ciclo) — carpeta: %s", SOURCE_DIR)
    logging.info("=" * 60)

    if not SOURCE_DIR.exists():
        logging.error("La carpeta fuente no existe: %s", SOURCE_DIR)
        sys.exit(1)

    videos = sorted(
        f for f in SOURCE_DIR.iterdir()
        if f.is_file()
        and f.suffix.lower() in SUPPORTED_EXTS
        and not f.name.endswith(".part")
    )

    if not videos:
        logging.info("No hay videos pendientes. Nada que hacer.")
        sys.exit(2)   # <-- código especial: 'vacío'

    logging.info("Pendientes: %s video(s). Procesando el primero.", len(videos))

    video = videos[0]

    # Verificar estabilidad del archivo (no se esté copiando)
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
        logging.info("CICLO OK — bash hara pausa de 720s antes del proximo.")
        sys.exit(0)
    else:
        logging.error("CICLO FALLO — bash hara pausa de 720s antes del reintento.")
        sys.exit(1)


if __name__ == "__main__":
    main()
