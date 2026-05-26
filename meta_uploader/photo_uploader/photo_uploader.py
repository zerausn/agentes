"""
photo_uploader.py
=================
Agente de subida masiva de fotos a Facebook como Reels.

Flujo:
  1. Escanea /media/zerausn/D69493CF9493B08B/Users/ZN-/Documents/ADM/Carpeta 1\\Fotos
  2. Ordena por tamanio DESCENDENTE (fotos mas pesadas primero)
  3. En cada ciclo, por el lote de 10 fotos:
       a. Crea UN Reel combinado de 30 segundos (las 10 fotos juntas) -> lo sube
       b. Ademas sube cada foto individualmente como Reel de 5s (10 Reels)
     Total: 11 publicaciones por ciclo.
  4. Mueve fotos procesadas a carpeta de exito
  5. Espera 15 minutos y repite

Autor: Antigravity
"""

import json
import logging
import os
import shutil
import sys
import time
import tempfile
from pathlib import Path

import requests

# ─── Rutas del módulo ─────────────────────────────────────────────────────────
BASE_DIR = Path(__file__).resolve().parent
PARENT_DIR = BASE_DIR.parent  # agentes/meta_uploader/

LOG_FILE = BASE_DIR / "photo_uploader.log"
HISTORIAL_FILE = BASE_DIR / "fotos_subidas.json"

# ─── Rutas de trabajo ─────────────────────────────────────────────────────────
DIR_FOTOS_IN = Path(r"/media/zerausn/D69493CF9493B08B/Users/ZN-/Documents/ADM/Carpeta 1\Fotos")
DIR_FOTOS_OUT = Path(r"/media/zerausn/D69493CF9493B08B/Users/ZN-/Documents/ADM/Carpeta 1\fotos_subidas_fb")
DIR_REELS_OUT = Path(r"/media/zerausn/D69493CF9493B08B/Users/ZN-/Documents/ADM/Carpeta 1\reels_generados_fb")

# ─── Configuración del agente ─────────────────────────────────────────────────
BATCH_SIZE = 10         # Fotos por ciclo
CYCLE_WAIT_SECONDS = 15 * 60  # 15 minutos entre ciclos
GRAPH_API_VERSION = "v19.0"
GRAPH_URL = f"https://graph.facebook.com/{GRAPH_API_VERSION}"
GRAPH_VIDEO_URL = f"https://graph-video.facebook.com/{GRAPH_API_VERSION}"

SUPPORTED_EXTS = {".jpg", ".jpeg", ".png", ".webp"}
HASHTAGS = "#PW #HQ #P"

# ─── Logging ──────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE, encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ],
)


# ─── Carga de credenciales desde el .env del módulo padre ─────────────────────
def _load_env():
    env_path = PARENT_DIR / ".env"
    env = {}
    if not env_path.exists():
        logging.error("[config] No se encontro .env en: %s", env_path)
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


# ─── Historial (evita re-subir fotos ya procesadas) ───────────────────────────
def cargar_historial() -> set:
    if not HISTORIAL_FILE.exists():
        return set()
    try:
        with open(HISTORIAL_FILE, "r", encoding="utf-8") as f:
            return set(json.load(f))
    except Exception:
        return set()


def guardar_historial(historial: set):
    with open(HISTORIAL_FILE, "w", encoding="utf-8") as f:
        json.dump(sorted(historial), f, indent=2, ensure_ascii=False)


# ─── Helpers de API ───────────────────────────────────────────────────────────
def _api_get(endpoint: str, params: dict) -> dict:
    """Hace un GET a la Graph API con reintentos básicos."""
    url = f"{GRAPH_URL}/{endpoint}"
    for intento in range(3):
        try:
            r = requests.get(url, params=params, timeout=60)
            return r.json()
        except Exception as exc:
            logging.warning("[api] GET fallo (intento %s/3): %s", intento + 1, exc)
            time.sleep(3 * (intento + 1))
    return {}


# ─── PASO 1: Inicializar sesión de subida de Reel ─────────────────────────────
def _reel_init_upload(file_size_bytes: int) -> tuple[str, str]:
    """
    Devuelve (video_id, upload_url) o lanza excepción.
    Endpoint: POST /{page_id}/video_reels  upload_phase=start
    """
    url = f"{GRAPH_URL}/{FB_PAGE_ID}/video_reels"
    payload = {
        "upload_phase": "start",
        "file_size": str(file_size_bytes),
        "access_token": FB_TOKEN,
    }
    r = requests.post(url, data=payload, timeout=60)
    data = r.json()

    if "error" in data:
        raise RuntimeError(f"Error al iniciar subida de Reel: {data['error']}")

    video_id = data.get("video_id")
    upload_url = data.get("upload_url")
    if not video_id or not upload_url:
        raise RuntimeError(f"Respuesta inesperada al iniciar Reel: {data}")

    logging.info("[reel] Sesion iniciada. video_id=%s", video_id)
    return str(video_id), str(upload_url)


# ─── PASO 2: Subir el archivo de video ────────────────────────────────────────
def _reel_upload_file(upload_url: str, video_path: Path) -> bool:
    """
    Sube el archivo MP4 al upload_url obtenido en el paso 1.
    Devuelve True si fue exitoso.
    """
    file_size = video_path.stat().st_size
    headers = {
        "Authorization": f"OAuth {FB_TOKEN}",
        "offset": "0",
        "file_size": str(file_size),
    }
    with open(video_path, "rb") as f:
        for intento in range(3):
            try:
                r = requests.post(
                    upload_url,
                    headers=headers,
                    data=f,
                    timeout=120,
                )
                if r.status_code == 200:
                    logging.info("[reel] Archivo subido correctamente.")
                    return True
                else:
                    logging.warning(
                        "[reel] Subida retorno estado %s: %s", r.status_code, r.text[:300]
                    )
            except Exception as exc:
                logging.warning("[reel] Error en subida (intento %s/3): %s", intento + 1, exc)
            f.seek(0)
            time.sleep(5 * (intento + 1))
    return False


# ─── PASO 3: Publicar el Reel ─────────────────────────────────────────────────
def _reel_publish(video_id: str, description: str) -> bool:
    """
    Finaliza y publica el Reel.
    Endpoint: POST /{page_id}/video_reels  upload_phase=finish
    Devuelve True si la publicación fue exitosa.
    """
    url = f"{GRAPH_URL}/{FB_PAGE_ID}/video_reels"
    payload = {
        "upload_phase": "finish",
        "video_id": video_id,
        "video_state": "PUBLISHED",
        "description": description,
        "access_token": FB_TOKEN,
    }
    for intento in range(3):
        r = requests.post(url, data=payload, timeout=60)
        data = r.json()
        if data.get("success") is True:
            logging.info("[reel] Reel publicado exitosamente. video_id=%s", video_id)
            return True
        if "error" in data:
            err = data["error"]
            logging.warning(
                "[reel] Error al publicar (intento %s/3): [%s] %s",
                intento + 1,
                err.get("code"),
                err.get("message"),
            )
            time.sleep(5 * (intento + 1))
        else:
            logging.warning("[reel] Respuesta inesperada al publicar: %s", data)
            time.sleep(5)
    return False


# ─── Subir UNA foto como Reel ─────────────────────────────────────────────────
def procesar_foto_individual(foto_path: Path, tmp_dir: Path) -> tuple[bool, Path | None]:
    """
    Convierte una foto a un Reel de 5s y la sube a Facebook.
    Devuelve (exito_subida, ruta_al_video_mp4).
    Esto permite reutilizar el MP4 generado para el Reel combinado posterior.
    """
    from photo_to_reel import convert_photo_to_reel

    # Generar descripción/caption
    nombre_base = foto_path.stem
    description = f"{nombre_base} {HASHTAGS}"

    logging.info(
        "[uploader] Procesando: %s (%.2f MB)",
        foto_path.name,
        foto_path.stat().st_size / 1_000_000,
    )

    # Convertir foto a MP4 
    video_temporal = tmp_dir / (foto_path.stem + "_reel.mp4")

    ok = convert_photo_to_reel(foto_path, video_temporal)
    if not ok:
        logging.error("[uploader] No se pudo convertir la foto a video: %s", foto_path.name)
        return False, None

    file_size = video_temporal.stat().st_size
    logging.info("[uploader] Video 5s generado: %.1f KB", file_size / 1024)

    # Paso 1: Iniciar sesión
    try:
        video_id, upload_url = _reel_init_upload(file_size)
    except RuntimeError as exc:
        logging.error("[uploader] Fallo al iniciar subida: %s", exc)
        return False, video_temporal

    # Paso 2: Subir archivo
    if not _reel_upload_file(upload_url, video_temporal):
        logging.error("[uploader] Fallo al subir el archivo de video.")
        return False, video_temporal

    # Paso 3: Publicar
    if not _reel_publish(video_id, description):
        logging.error("[uploader] Fallo al publicar el Reel.")
        return False, video_temporal

    return True, video_temporal


# ─── Ciclo principal ──────────────────────────────────────────────────────────
def ciclo_de_subida():
    """Escanea la carpeta de entrada y procesa hasta BATCH_SIZE fotos.
    
    Por ciclo se suben:
    - 1 Reel combinado de 30 segundos (todas las fotos del lote juntas)
    - 10 Reels individuales de 5 segundos (uno por foto)
    Total: 11 publicaciones por ciclo de 15 minutos.
    """
    from photo_to_reel import convert_video_clips_to_combined_reel

    historial = cargar_historial()
    DIR_FOTOS_OUT.mkdir(parents=True, exist_ok=True)

    # Obtener fotos pendientes, ordenadas por tamanio DESC (mas pesadas primero)
    todas = [
        p for p in DIR_FOTOS_IN.glob("*.*")
        if p.suffix.lower() in SUPPORTED_EXTS and p.stem not in historial
    ]
    todas.sort(key=lambda p: p.stat().st_size, reverse=True)

    if not todas:
        logging.info("[ciclo] No hay fotos pendientes en la carpeta de entrada.")
        return 0

    lote = todas[:BATCH_SIZE]
    logging.info(
        "[ciclo] Iniciando lote: %s fotos (de %s pendientes total)",
        len(lote), len(todas)
    )

    # ── PASO A: 10 Reels INDIVIDUALES de 5 segundos ──────────────────────────
    logging.info("[ciclo] Paso A: Subiendo %s Reels individuales de 5s...", len(lote))
    subidas_ok = 0
    videos_para_combinar = []

    DIR_REELS_OUT.mkdir(parents=True, exist_ok=True)

    for foto in lote:
        exito, vid_path = procesar_foto_individual(foto, DIR_REELS_OUT)
        if vid_path and vid_path.exists():
            videos_para_combinar.append(vid_path)
            
        if exito:
            destino = DIR_FOTOS_OUT / foto.name
            try:
                if destino.exists():
                    foto.unlink()
                else:
                    shutil.move(str(foto), str(destino))
                logging.info("[ciclo] Foto movida a: %s", destino)
            except Exception as exc:
                logging.warning("[ciclo] No se pudo mover %s: %s", foto.name, exc)

            historial.add(foto.stem)
            guardar_historial(historial)
            subidas_ok += 1
        else:
            logging.error("[ciclo] Fallo al subir individual: %s. Se omite el movimiento.", foto.name)

        time.sleep(2)

    # ── PASO B: Reel COMBINADO de 30 segundos usando clips de Paso A ──
    if videos_para_combinar:
        logging.info("[ciclo] Paso B: Armando Reel combinado de 30s con %s clips pre-renderizados...", len(videos_para_combinar))
        
        # Le damos un nombre unico para no sobreescribir el archivo en futuros ciclos
        timestamp_str = time.strftime("%Y%m%d_%H%M%S")
        reel_combinado = DIR_REELS_OUT / f"reel_combinado_30s_{timestamp_str}.mp4"
        
        ok_combinado = convert_video_clips_to_combined_reel(videos_para_combinar, reel_combinado, total_duration=30)

        if ok_combinado:
            desc_combinado = "#PW #HQ #PC"
            file_size = reel_combinado.stat().st_size
            try:
                video_id, upload_url = _reel_init_upload(file_size)
                if _reel_upload_file(upload_url, reel_combinado):
                    if _reel_publish(video_id, desc_combinado):
                        logging.info("[ciclo] Reel combinado publicado exitosamente.")
                    else:
                        logging.error("[ciclo] Fallo al publicar el Reel combinado.")
                else:
                    logging.error("[ciclo] Fallo al subir el archivo del Reel combinado.")
            except RuntimeError as exc:
                logging.error("[ciclo] Error iniciando subida combinada: %s", exc)
        else:
            logging.error("[ciclo] No se pudo crear el Reel combinado rapido.")
    else:
        logging.error("[ciclo] No hubo videos validos generados en la fase A para armar el reel agrupado.")

    logging.info(
        "[ciclo] Lote completado: %s/%s Reels individuales listos.",
        subidas_ok, len(lote)
    )
    return subidas_ok


def main():
    print("=" * 60)
    print("  ANTIGRAVITY - SUBIDOR MASIVO DE FOTOS A FACEBOOK (REELS)")
    print("=" * 60)

    if not FB_PAGE_ID or not FB_TOKEN:
        logging.error("Credenciales no configuradas. Verifica el archivo .env en meta_uploader/")
        sys.exit(1)

    if not DIR_FOTOS_IN.exists():
        logging.error("La carpeta de fotos de entrada no existe: %s", DIR_FOTOS_IN)
        sys.exit(1)

    logging.info("Carpeta de entrada : %s", DIR_FOTOS_IN)
    logging.info("Carpeta de salida  : %s", DIR_FOTOS_OUT)
    logging.info("Lote por ciclo     : %s fotos", BATCH_SIZE)
    logging.info("Espera entre ciclos: %s minutos", CYCLE_WAIT_SECONDS // 60)
    logging.info("-" * 60)

    ciclo_num = 0
    while True:
        ciclo_num += 1
        logging.info("===== CICLO #%s =====", ciclo_num)
        subidas = ciclo_de_subida()

        if subidas == 0:
            logging.info("No hay mas fotos. El agente revisara de nuevo en %s min...", CYCLE_WAIT_SECONDS // 60)

        logging.info("Esperando %s minutos hasta el siguiente ciclo...", CYCLE_WAIT_SECONDS // 60)
        time.sleep(CYCLE_WAIT_SECONDS)


if __name__ == "__main__":
    main()
