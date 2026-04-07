import json
import logging
import os
import subprocess
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent
LOG_FILE = BASE_DIR / "classifier.log"
SUPPORTED_SUFFIXES = {".mp4", ".mov"}


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(message)s",
    handlers=[logging.FileHandler(LOG_FILE, encoding="utf-8"), logging.StreamHandler()],
)


def check_video_properties(filepath):
    """
    Usa ffprobe para obtener width, height y duration con una sola llamada.
    """
    cmd = [
        "ffprobe",
        "-v",
        "error",
        "-select_streams",
        "v:0",
        "-show_entries",
        "stream=width,height,duration",
        "-of",
        "json",
        filepath,
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        data = json.loads(result.stdout)
        streams = data.get("streams", [])
        if not streams:
            return None

        stream = streams[0]
        return {
            "width": int(stream.get("width", 0)),
            "height": int(stream.get("height", 0)),
            "duration": float(stream.get("duration", 0)),
        }
    except Exception as exc:
        logging.error("Error inspeccionando %s: %s", filepath, exc)
        return None


def is_shared_safe_reel(props):
    """
    Politica local conservadora para el carril compartido FB Reel + IG Reel.
    No representa todos los limites de IG; solo el subconjunto seguro comun.
    """
    if not props:
        return False

    width = props["width"]
    height = props["height"]
    duration = props["duration"]

    if not (3.0 <= duration <= 90.0):
        return False

    if width <= 0 or height <= 0 or height <= width:
        return False

    ratio = width / height
    return abs(ratio - (9 / 16)) <= 0.08


def iter_video_files(target_path):
    for file_path in target_path.rglob("*"):
        if file_path.is_file() and file_path.suffix.lower() in SUPPORTED_SUFFIXES:
            yield file_path


def classify_directory(target_dir):
    reels_data = []
    posts_data = []
    target_path = Path(target_dir).resolve()

    logging.info("Escaneando %s en busca de videos compatibles...", target_path)

    for video_file in iter_video_files(target_path):
        props = check_video_properties(str(video_file))
        if not props:
            continue

        file_size = os.path.getsize(video_file)
        item = (str(video_file), file_size)
        if is_shared_safe_reel(props):
            reels_data.append(item)
            logging.info(
                "[REEL] %s | %.2f MB | %.2fs | %sx%s",
                video_file.name,
                file_size / 1e6,
                props["duration"],
                props["width"],
                props["height"],
            )
        else:
            posts_data.append(item)
            logging.info(
                "[POST] %s | %.2f MB | %.2fs | %sx%s",
                video_file.name,
                file_size / 1e6,
                props["duration"],
                props["width"],
                props["height"],
            )

    reels_data.sort(key=lambda item: item[1], reverse=True)
    posts_data.sort(key=lambda item: item[1], reverse=True)

    reels_paths = [item[0] for item in reels_data]
    posts_paths = [item[0] for item in posts_data]

    with open(BASE_DIR / "pendientes_reels.json", "w", encoding="utf-8") as handle:
        json.dump(reels_paths, handle, indent=2, ensure_ascii=False)
    with open(BASE_DIR / "pendientes_posts.json", "w", encoding="utf-8") as handle:
        json.dump(posts_paths, handle, indent=2, ensure_ascii=False)

    logging.info(
        "Clasificacion finalizada. Reels compartidos: %s | Posts/otros: %s",
        len(reels_paths),
        len(posts_paths),
    )


if __name__ == "__main__":
    import sys

    directory = sys.argv[1] if len(sys.argv) > 1 else "."
    classify_directory(directory)
