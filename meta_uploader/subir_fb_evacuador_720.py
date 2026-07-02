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
LOG_FILE   = BASE_DIR / "fb_evacuador.log"

TEASER_RE      = re.compile(r"(?i)_teaser_\d+")
SUPPORTED_EXTS = {".mp4", ".mov", ".mkv"}

# Margen de tolerancia al comparar con la relacion 9:16 exacta (igual al clasificador)
REEL_ASPECT_TOLERANCE = 0.08

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
    Reutiliza la misma politica conservadora que classify_meta_videos.py.
    Si ffprobe falla, asume que NO es reel-safe (fallback a POST estandar).
    """
    width, height = probe_video_dimensions(video_path)
    if not width or not height or height <= width:
        # No pudimos detectar o es horizontal: no es apto para Reel
        return False
    ratio = width / height
    return abs(ratio - (9 / 16)) <= REEL_ASPECT_TOLERANCE


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
    caption   = build_caption(video_path)
    is_teaser = bool(TEASER_RE.search(video_path.stem))

    if is_teaser and is_reel_safe(video_path):
        logging.info("Subiendo como REEL de Facebook (teaser vertical 9:16): %s", video_path.name)
        result = upload_fb_reel(str(video_path), caption)
    elif is_teaser:
        # Teaser horizontal o sin datos de dimensiones: sube como POST estandar
        # para evitar el rechazo del endpoint video_reels que exige 9:16.
        logging.info(
            "Teaser NO es vertical 9:16 — subiendo como VIDEO ESTANDAR: %s",
            video_path.name,
        )
        result = upload_fb_video_standard(str(video_path), caption)
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
        move_to_failed(video)
        logging.error("CICLO FALLO — video movido a fallidos_facebook para no bloquear la cola. Bash hara pausa de 720s.")
        sys.exit(1)


if __name__ == "__main__":
    main()
