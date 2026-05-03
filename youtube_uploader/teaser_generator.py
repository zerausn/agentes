import json
import logging
import os
import subprocess
from pathlib import Path

from video_helpers import load_config

# Configuracion General
BASE_DIR = Path(__file__).resolve().parent
JSON_DB = BASE_DIR / "scanned_videos.json"
LOG_FILE = BASE_DIR / "teaser_generator.log"

config = load_config(BASE_DIR)
TEASERS_DIR = Path(config.get("teaser_input_directory", "/tmp/teasers"))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[logging.FileHandler(LOG_FILE), logging.StreamHandler()],
)

TEASER_DURATION_SEC = 16      # duracion de cada parte en segundos

def get_video_duration(input_file):
    from video_helpers import resolve_ffprobe_binary
    ffprobe = resolve_ffprobe_binary(BASE_DIR)
    result = subprocess.run(
        [str(ffprobe), "-v", "error", "-select_streams", "v:0",
         "-show_entries", "stream=duration", "-of", "csv=p=0", str(input_file)],
        capture_output=True, text=True, check=False
    )
    try:
        return float(result.stdout.strip().rstrip(","))
    except (ValueError, AttributeError):
        return 0.0

def build_ffmpeg_teaser_cmd(input_file, start_sec, output_path):
    from video_helpers import resolve_ffmpeg_binary
    ffmpeg = resolve_ffmpeg_binary(BASE_DIR)
    return [
        str(ffmpeg), "-y",
        "-ss", str(round(start_sec, 3)),
        "-i", str(input_file),
        "-t", str(TEASER_DURATION_SEC),
        "-vf", "scale=trunc(iw/2)*2:trunc(ih/2)*2",
        "-c:v", "libx264", "-crf", "18", "-preset", "veryfast",
        "-c:a", "aac", "-b:a", "128k", "-movflags", "+faststart",
        str(output_path),
    ]

def generate_teasers_for_video(file_path, base_name):
    """Parte el video completo en segmentos CONSECUTIVOS de TEASER_DURATION_SEC segundos."""
    duration = get_video_duration(file_path)
    if duration <= 0:
        logging.error("No se pudo obtener la duracion de %s", file_path.name)
        return []

    # Bloques consecutivos: 0->16, 16->32, 32->48 ...
    starts = []
    t = 0.0
    while t + TEASER_DURATION_SEC <= duration:
        starts.append(t)
        t += TEASER_DURATION_SEC

    if not starts:
        starts = [0]

    logging.info(
        "Video: %s | Duracion: %.1fs | Partes de %ss -> %s segmentos totales",
        file_path.name, duration, TEASER_DURATION_SEC, len(starts)
    )

    generated = []
    for idx, start in enumerate(starts, start=1):
        out_path = TEASERS_DIR / f"{base_name}_teaser_{idx}.mp4"
        if out_path.exists():
            logging.info("  [SKIP] Parte %s ya existe: %s", idx, out_path.name)
            generated.append(out_path)
            continue
        cmd = build_ffmpeg_teaser_cmd(file_path, start, out_path)
        result = subprocess.run(cmd, capture_output=True, text=True, check=False)
        if result.returncode == 0:
            logging.info(
                "  [OK] Parte %s/%s -> %s (s%s - s%s)",
                idx, len(starts), out_path.name, round(start), round(start + TEASER_DURATION_SEC)
            )
            generated.append(out_path)
        else:
            logging.error("  [ERROR] Parte %s fallo: %s", idx, result.stderr[-300:])
    return generated

def get_terminal_emulator():
    import shutil
    for term in ["qterminal", "x-terminal-emulator", "gnome-terminal", "xterm"]:
        if shutil.which(term):
            return term
    return None

def launch_granular_window(terminal, title, python_bin, script_path, extra_args=[]):
    """Lanza un proceso en una nueva ventana de terminal."""
    cmd_list = [str(python_bin), str(script_path)] + extra_args
    # Escapamos los espacios para el comando de bash
    cmd_str = " ".join([f'"{arg}"' for arg in cmd_list])
    
    # Comando interno que pone el título y ejecuta el script de python
    bash_script = f"echo -ne '\\033]0;{title}\\007'; {cmd_str}; echo ''; echo -e '\\e[32m[!] Proceso finalizado. Esta ventana se cerrara en 15 segundos...\\e[0m'; sleep 15"
    
    if terminal in ["qterminal", "x-terminal-emulator"]:
        # NOTA: Pasamos los argumentos de bash por separado en la lista de Popen
        # ['qterminal', '-e', 'bash', '-c', '...']
        return subprocess.Popen([terminal, "-e", "bash", "-c", bash_script])
    else:
        # Fallback normal si no hay terminal GUI
        return subprocess.Popen(cmd_list)

def load_db():
    if not JSON_DB.exists():
        return []
    with JSON_DB.open("r", encoding="utf-8") as f:
        return json.load(f)

def save_db(data):
    with JSON_DB.open("w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)

def main():
    logging.info("=" * 60)
    logging.info(" INICIANDO GENERADOR DE TEASERS (CORTES DE 16 SEG)")
    logging.info("=" * 60)

    videos = load_db()
    TEASERS_DIR.mkdir(exist_ok=True)

    cambios = False
    
    for video in videos:
        # Solo videos largos o no marcados como short (teasers son para videos crudos)
        # Tambien omitimos si ya hemos generado teasers o si ya está subido.
        # Es comun que haya crudos largos. Filtramos duration > 180 si existe, o v_type == 'video'
        
        is_video = video.get("type", "video") == "video"
        duration = video.get("duration", 999) # Si no hay duracion asume grande
        
        if video.get("uploaded"):
            continue
            
        if not is_video and duration <= 180:
            continue
            
        file_path = Path(video.get("path", ""))
        if not file_path.exists():
            continue

        logging.info(f"Generando teasers para: {file_path.name}")
        
        # Output pattern: Teasers_pendientes / NOMBREORIGINAL_teaser_%03d.mp4
        # El suffix es .mp4 para asegurarnos compatibilidad
        base_name = file_path.stem
        existing_teasers = sorted(TEASERS_DIR.glob(f"{base_name}_teaser_*.mp4"))
        
        skip_generation = False
        if existing_teasers:
            logging.info(
                "Ya existen %s teasers pendientes para %s. Se omite regeneracion.",
                len(existing_teasers),
                file_path.name,
            )
            video["teasers_generated"] = True
            cambios = True
            skip_generation = True
        
        if not skip_generation:
            generated = generate_teasers_for_video(file_path, base_name)
            if generated:
                logging.info(
                    "Generacion completa para %s: %s teaser(s) en cola.",
                    file_path.name, len(generated)
                )
                video["teasers_generated"] = True
                cambios = True
            else:
                logging.error("No se genero ningun teaser para %s. Abortando este video.", file_path.name)
                continue

        # --- LANZAR CARGADORES EN PARALELO (Crudo y Teasers) ---
        try:
            # Rutas
            teaser_script = BASE_DIR / "teaser_uploader.py"
            crudo_script = BASE_DIR / "uploader.py"
            
            # Deteccion de Binario Python (PC vs Termux)
            python_bin = BASE_DIR.parent.parent / ".venv/bin/python3"
            if os.environ.get('PREFIX') and 'com.termux' in os.environ.get('PREFIX', ''):
                python_bin = "python3"
            elif not python_bin.exists():
                python_bin = "python3" # Fallback
                
            logging.info(f"Lanzando CARGADORES EN PARALELO para: {file_path.name}")
            
            term = get_terminal_emulator()
            source_stem = file_path.stem
            
            # 1. Iniciar subida de Crudo (En nueva ventana)
            p_crudo = launch_granular_window(
                term, 
                f"CRUDO: {file_path.name}", 
                python_bin, 
                crudo_script, 
                ["--video", str(file_path), "--from-orchestrator"]
            )
            
            # 2. Iniciar subida de Teasers (En nueva ventana)
            p_teaser = launch_granular_window(
                term, 
                f"TEASERS: {source_stem}", 
                python_bin, 
                teaser_script, 
                ["--source-video", source_stem, "--from-orchestrator"]
            )
            
            logging.info("Esperando confirmacion HD simultanea de Crudo y Teasers...")
            
            # Esperar ambos
            p_crudo.wait()
            p_teaser.wait()
            
            # Validacion Estricta: Verificar si uploader marco el archivo como subido
            # Si fallo por Cuota o limite diario, uploaded seguira siendo False u omitido.
            current_db = load_db()
            uploaded_success = False
            for v in current_db:
                if v["path"] == str(file_path):
                    uploaded_success = v.get("uploaded", False)
                    break
            
            if not uploaded_success:
                logging.error(f"El video {file_path.name} no se marcó como subido. Abortando el lote por posible límite de cuota o error fatal.")
                break
            
            logging.info(f"Ciclo completo para {file_path.name} finalizado (HD confirmado y movido).")
        except Exception as e:
            logging.error(f"Error en la orquestacion paralela de {file_path.name}: {e}")

    if cambios:
        save_db(videos)
        
    logging.info("Generación de teasers finalizada.")

if __name__ == "__main__":
    main()
