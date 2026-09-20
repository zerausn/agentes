"""
subir_fb_evacuador_crudos.py  (VERSION BASH-LOOP — sin time.sleep interno)
Evacua UN SOLO VIDEO CRUDO de 'videos subidos exitosamente' a Facebook y retorna.
El loop/pausa de 720s lo gestiona el script bash (con termux-wake-lock).

SOLO CRUDOS → Performatic Writings Cali (ID: 803559979506784)

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
LOG_FILE   = BASE_DIR / "fb_evacuador_crudos.log"

TEASER_RE      = re.compile(r"(?i)_teaser_\d+")
SUPPORTED_EXTS = {".mp4", ".mov", ".mkv"}

# Margen de tolerancia al comparar con la relacion 9:16 exacta (igual al clasificador)
REEL_ASPECT_TOLERANCE = 0.08

# --- IDs de páginas de Facebook ---
FB_PAGE_ID_RAW = os.environ.get("META_FB_PAGE_ID_RAW", "803559979506784")           # Performatic Writings Cali
FB_PAGE_TOKEN_RAW = os.environ.get("META_FB_PAGE_TOKEN_RAW", os.environ.get("META_FB_PAGE_TOKEN", ""))

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
    caption = build_caption(video_path)
    page_id = FB_PAGE_ID_RAW
    page_token = FB_PAGE_TOKEN_RAW
    page_name = "Performatic Writings Cali (Crudos)"

    if not page_id or not page_token:
        logging.error("Faltan credenciales para la página %s (page_id=%s, token=%s)",
                      page_name, page_id, "OK" if page_token else "FALTANTE")
        return False

    # CRUDOS: Reel si es 9:16, sino video estándar
    if is_reel_safe(video_path):
        logging.info("Subiendo CRUDO como REEL de Facebook a %s: %s", page_name, video_path.name)
        result = upload_fb_reel(str(video_path), caption, page_id=page_id, page_token=page_token)
    else:
        logging.info("Subiendo CRUDO como VIDEO ESTANDAR de Facebook a %s: %s", page_name, video_path.name)
        result = upload_fb_video_standard(str(video_path), caption, page_id=page_id, page_token=page_token)

    if result:
        logging.info("Subida exitosa | video_id=%s | archivo=%s | página=%s", result, video_path.name, page_name)
        return True
    else:
        logging.error("Fallo la subida de: %s a página %s", video_path.name, page_name)
        return False


def main():
    logging.info("=" * 60)
    logging.info("  FB EVACUADOR CRUDOS (1 video/ciclo) — carpeta: %s", SOURCE_DIR)
    logging.info("  Crudos -> Performatic Writings Cali (803559979506784)")
    logging.info("=" * 60)

    if not SOURCE_DIR.exists():
        logging.error("La carpeta fuente no existe: %s", SOURCE_DIR)
        sys.exit(1)

    # Solo videos SIN _teaser_
    videos = sorted(
        f for f in SOURCE_DIR.iterdir()
        if f.is_file()
        and f.suffix.lower() in SUPPORTED_EXTS
        and not f.name.endswith(".part")
        and not TEASER_RE.search(f.stem)
    )

    if not videos:
        logging.info("No hay videos CRUDOS pendientes. Nada que hacer.")
        sys.exit(2)

    logging.info("Pendientes CRUDOS: %s video(s). Procesando el primero.", len(videos))

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