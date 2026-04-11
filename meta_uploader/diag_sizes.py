import argparse
import os
from pathlib import Path


def list_biggest_videos(target_dir, limit):
    target_path = Path(target_dir).resolve()
    videos = []

    for file_path in target_path.rglob("*"):
        if not file_path.is_file() or file_path.suffix.lower() not in {".mp4", ".mov"}:
            continue
        try:
            videos.append((file_path, os.path.getsize(file_path)))
        except OSError:
            continue

    videos.sort(key=lambda item: item[1], reverse=True)

    print(f"Top {min(limit, len(videos))} videos mas pesados en {target_path}:")
    for file_path, size in videos[:limit]:
        print(f"{file_path} | {size / (1024 * 1024):.2f} MB")


def main():
    parser = argparse.ArgumentParser(description="Lista los videos mas pesados de una carpeta.")
    parser.add_argument("target_dir", help="Carpeta a inspeccionar")
    parser.add_argument("--limit", type=int, default=20, help="Cantidad maxima a mostrar")
    args = parser.parse_args()
    list_biggest_videos(args.target_dir, args.limit)


if __name__ == "__main__":
    main()
