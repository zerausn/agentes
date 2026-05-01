import os
import subprocess
import logging
from pathlib import Path
import time
import shutil

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

# --- Directorios Fijos ---
BASE_DIR = Path(__file__).resolve().parent

DIR_FOTOS_IN = Path(r"/media/zerausn/D69493CF9493B08B/Users/ZN-/Documents\ADM\FOTOs")
DIR_FOTOS_OUT = Path(r"/media/zerausn/D69493CF9493B08B/Users/ZN-/Documents\ADM\FOTOS_4K_MEJORADAS")

DIR_VIDEOS_IN = Path(r"/media/zerausn/D69493CF9493B08B/Users/ZN-/Documents\ADM\Nueva carpeta")
DIR_VIDEOS_OUT = Path(r"/media/zerausn/D69493CF9493B08B/Users/ZN-/Documents\ADM\VIDEOS_MEJORADOS")

# --- Rutas de Motores ---
NCNN_BIN = BASE_DIR / "bin" / "realesrgan-ncnn-vulkan.exe"
VENV_PYTHON = BASE_DIR / ".venv" / "Scripts" / "python.exe"
SCRIPT_FAST = BASE_DIR / "tools" / "upscaling" / "scripts" / "upscale_video_fast.py"

def setup_dirs():
    """Crea los directorios de salida si no existen."""
    DIR_FOTOS_OUT.mkdir(parents=True, exist_ok=True)
    DIR_VIDEOS_OUT.mkdir(parents=True, exist_ok=True)
    logging.info(f"Directorio de salida de FOTOS: {DIR_FOTOS_OUT}")
    logging.info(f"Directorio de salida de VIDEOS: {DIR_VIDEOS_OUT}")

def procesar_fotos_masivo():
    """Usa el binario NCNN para procesar toda la carpeta de fotos de forma nativa."""
    if not DIR_FOTOS_IN.exists():
        logging.warning("No se encontro la carpeta de fotos de entrada.")
        return

    fotos = list(DIR_FOTOS_IN.glob("*.*"))
    if not fotos:
        logging.info("No hay fotos que procesar en la carpeta.")
        return

    logging.info(f"==========================================")
    logging.info(f" INICIANDO TRABAJO: ESCALADO DE FOTOS CON IA")
    logging.info(f"==========================================")
    
    # NCNN maneja carpetas nativamente, esto es súper rápido
    cmd = [
        str(NCNN_BIN),
        "-i", str(DIR_FOTOS_IN),
        "-o", str(DIR_FOTOS_OUT),
        "-s", "4",
        "-n", "realesrgan-x4plus"
    ]
    
    logging.info(f"Invocando IA Nativa... (Esto tomara un tiempo dependiendo de la CPU)")
    process = subprocess.run(cmd)
    
    if process.returncode == 0:
        logging.info("✅ Procesamiento masivo de Fotos completado.")
    else:
        logging.error("❌ Error en el procesamiento de fotos.")

def procesar_videos_masivo():
    """Itera sobre la carpeta de videos y lanza el script FFmpeg para cada uno."""
    if not DIR_VIDEOS_IN.exists():
        logging.warning("No se encontro la carpeta de videos de entrada.")
        return
        
    extensiones_video = {".mp4", ".mkv", ".avi", ".mov", ".webm"}
    videos = [p for p in DIR_VIDEOS_IN.glob("*.*") if p.suffix.lower() in extensiones_video]
    
    if not videos:
        logging.info("No hay videos que procesar en la carpeta.")
        return

    logging.info(f"\n==========================================")
    logging.info(f" INICIANDO TRABAJO: ESCALADO RÁPIDO DE {len(videos)} VIDEOS")
    logging.info(f"==========================================")

    for i, video_path in enumerate(videos, 1):
        output_name = video_path.stem + "_4k" + video_path.suffix
        output_path = DIR_VIDEOS_OUT / output_name
        
        # Evitar re-procesar si ya se terminó antes (permite pausar y reanudar este script)
        if output_path.exists() and output_path.stat().st_size > 0:
            logging.info(f"[{i}/{len(videos)}] Saltando (ya existe): {output_name}")
            continue
            
        logging.info(f"[{i}/{len(videos)}] Procesando video: {video_path.name} ...")
        
        cmd = [
            str(VENV_PYTHON),
            str(SCRIPT_FAST),
            "-i", str(video_path),
            "-o", str(output_path),
            "--preset", "4k",
            "--sharpen"
        ]
        
        result = subprocess.run(cmd)
        if result.returncode != 0:
            logging.error(f"❌ Falló el procesamiento de: {video_path.name}")
        else:
            logging.info(f"✅ Terminado: {output_name}")

import argparse

def main():
    parser = argparse.ArgumentParser(description="Procesador Masivo de Medios")
    parser.add_argument("--fotos", action="store_true", help="Procesar solo la cola de fotos")
    parser.add_argument("--videos", action="store_true", help="Procesar solo la cola de videos")
    args = parser.parse_args()

    print(r"""
     ___      _       __  __           _            
    | _ )_  _| |__ __|  \/  |__ _ _____| |_ ___ _ _ 
    | _ \ || | / _/ _ \ |\/| / _` (_-<_-<  _/ -_) '_|
    |___/\_,_|_\__\___/_|  |_\__,_/__/__/\__\___|_| 
                                                    
    Antigravity - Procesador Masivo de Medios (Upscaling)
    """)
    
    # 1. Asegurar la existencia e integridad del ecosistema operativo
    if not NCNN_BIN.exists() or not VENV_PYTHON.exists():
        logging.error("El entorno no esta completo. Faltan binarios o dependencias .venv.")
        return
        
    setup_dirs()
    
    # Si no se pasan argumentos, procesamos todo por defecto
    run_all = not args.fotos and not args.videos
    
    tasks_run = []
    
    # 2. Cola de trabajo: Fotos
    if args.fotos or run_all:
        logging.info("=> Iniciando engine de Fotos.")
        procesar_fotos_masivo()
        tasks_run.append(DIR_FOTOS_OUT)
    
    # 3. Cola de trabajo: Videos
    if args.videos or run_all:
        logging.info("=> Iniciando engine de Videos.")
        procesar_videos_masivo()
        tasks_run.append(DIR_VIDEOS_OUT)
    
    logging.info(f"\n==========================================")
    logging.info(f" 🎉 TAREAS FINALIZADAS EXITOSAMENTE!")
    for out_dir in tasks_run:
        logging.info(f" Revisa la carpeta: {out_dir}")
    logging.info(f"==========================================")

if __name__ == "__main__":
    main()
