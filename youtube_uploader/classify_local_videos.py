import logging
from pathlib import Path

from video_helpers import enrich_video_record
from video_helpers import load_json_file
from video_helpers import save_json_file

BASE_DIR = Path(__file__).resolve().parent
JSON_DB = BASE_DIR / "scanned_videos.json"

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")


def main():
    if not JSON_DB.exists():
        logging.error("No se encontro scanned_videos.json")
        return

    videos = load_json_file(JSON_DB, [])
    stats = {"short": 0, "video": 0, "error": 0, "updated": 0}

    for video in videos:
        if video.get("uploaded", False):
            continue

        file_path = Path(video["path"])
        if not file_path.exists():
            logging.warning("Archivo no encontrado: %s", file_path)
            continue

        changed = enrich_video_record(video, include_probe=True)
        if video.get("type") in {"short", "video"}:
            stats[video["type"]] += 1
        else:
            stats["error"] += 1

        if changed:
            stats["updated"] += 1

    save_json_file(JSON_DB, videos)

    print("\n--- RESUMEN DE CLASIFICACION LOCAL ---")
    print(f"Shorts detectados: {stats['short']}")
    print(f"Videos normales: {stats['video']}")
    print(f"Registros actualizados: {stats['updated']}")
    print(f"Errores: {stats['error']}")


if __name__ == "__main__":
    main()
