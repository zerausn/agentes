import logging
import os
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from video_helpers import ensure_basic_video_fields
from video_helpers import get_video_roots
from video_helpers import is_ephemeral_video_artifact
from video_helpers import load_config
from video_helpers import load_json_file
from video_helpers import save_json_file

BASE_DIR = Path(__file__).resolve().parent
LOG_FILE = BASE_DIR / "scanner.log"
OUTPUT_JSON = BASE_DIR / "scanned_videos.json"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[logging.FileHandler(LOG_FILE), logging.StreamHandler()],
)

config = load_config(BASE_DIR)
scanner_cfg = config.get("scanner", {})

VIDEO_EXTENSIONS = {extension.lower() for extension in scanner_cfg.get("video_extensions", [".mp4", ".mkv", ".avi", ".mov", ".wmv", ".flv"])}
MIN_SIZE_MB = scanner_cfg.get("min_size_mb", 100)
EXCLUDE_FOLDERS = {folder.lower() for folder in scanner_cfg.get("exclude_folders", [])}
EXCLUDE_FILES = {filename.lower() for filename in scanner_cfg.get("exclude_files", [])}
EXCLUDE_PATTERNS = [pattern.lower() for pattern in scanner_cfg.get("exclude_patterns", [])]


def scan_directory(directory):
    found = []
    logging.info("Escaneando: %s", directory)

    for root, dirs, files in os.walk(directory):
        dirs[:] = [name for name in dirs if name.lower() not in EXCLUDE_FOLDERS]

        for filename in files:
            ext = os.path.splitext(filename)[1].lower()
            if ext not in VIDEO_EXTENSIONS:
                continue

            filename_lower = filename.lower()
            if is_ephemeral_video_artifact(filename_lower):
                continue
            if filename_lower in EXCLUDE_FILES:
                continue
            if any(pattern in filename_lower for pattern in EXCLUDE_PATTERNS):
                continue

            file_path = Path(root) / filename
            try:
                size_mb = file_path.stat().st_size / (1024 * 1024)
            except OSError:
                continue

            if size_mb < MIN_SIZE_MB:
                continue

            video = {
                "path": str(file_path),
                "size_mb": round(size_mb, 2),
                "filename": filename,
                "uploaded": False,
            }
            ensure_basic_video_fields(video)
            found.append(video)

    return found


def merge_scan_results(existing_videos, discovered_videos):
    existing_by_path = {video["path"]: video for video in existing_videos}

    for video in existing_videos:
        try:
            ensure_basic_video_fields(video)
        except OSError:
            continue

    new_count = 0
    for discovered in discovered_videos:
        known = existing_by_path.get(discovered["path"])
        if known:
            for field in ("size_mb", "filename", "creation_date"):
                if discovered.get(field):
                    known[field] = discovered[field]
            continue

        existing_videos.append(discovered)
        existing_by_path[discovered["path"]] = discovered
        new_count += 1

    existing_videos.sort(key=lambda item: item.get("size_mb", 0), reverse=True)
    return new_count


def main():
    existing_videos = load_json_file(OUTPUT_JSON, [])
    roots_to_scan = get_video_roots(BASE_DIR, config=config, videos=existing_videos)
    if not roots_to_scan:
        logging.error(
            "No hay rutas de video configuradas. Define scanner.video_roots en config.json o la variable YOUTUBE_UPLOADER_VIDEO_ROOTS."
        )
        return

    logging.info("Iniciando escaneo multihilo en %s raices...", len(roots_to_scan))

    all_found = []
    with ThreadPoolExecutor() as executor:
        for result in executor.map(scan_directory, roots_to_scan):
            all_found.extend(result)

    new_count = merge_scan_results(existing_videos, all_found)
    save_json_file(OUTPUT_JSON, existing_videos)
    logging.info("Escaneo finalizado. %s nuevos, %s totales.", new_count, len(existing_videos))


if __name__ == "__main__":
    main()
