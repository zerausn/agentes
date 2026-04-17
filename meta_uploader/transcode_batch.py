import argparse
import json
import os
import subprocess
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = BASE_DIR / "optimized_videos"


def load_queue(source_file):
    with open(BASE_DIR / source_file, "r", encoding="utf-8") as handle:
        return json.load(handle)


def transcode_batch(limit=10, source_file="pendientes_reels.json"):
    OUTPUT_DIR.mkdir(exist_ok=True)
    queue = load_queue(source_file)
    batch = queue[:limit]
    optimized_list = []

    print(f"Transcodificando {len(batch)} videos desde {source_file}...")
    for video_path in batch:
        filename = os.path.basename(video_path)
        output_path = OUTPUT_DIR / f"opt_{filename}"

        if output_path.exists() and output_path.stat().st_size > 0:
            print(f"Saltando, ya existe: {filename}")
            optimized_list.append(str(output_path))
            continue
        if output_path.exists():
            print(f"Reprocesando copia corrupta o vacia: {filename}")
            output_path.unlink()

        print(f"Procesando: {filename}")
        cmd = [
            "ffmpeg",
            "-y",
            "-i",
            video_path,
            "-vf",
            "scale='if(gt(iw,ih),1920,-2)':'if(gt(iw,ih),-2,1080)'",
            "-c:v",
            "libx264",
            "-crf",
            "23",
            "-preset",
            "ultrafast",
            "-c:a",
            "aac",
            "-b:a",
            "128k",
            "-hide_banner",
            "-loglevel",
            "info",
            "-stats",
            str(output_path),
        ]
        try:
            subprocess.run(cmd, check=True)
            optimized_list.append(str(output_path))
            print(f"OK: {filename}")
        except Exception as exc:
            print(f"Error en {filename}: {exc}")

    with open(BASE_DIR / "pendientes_optimizado.json", "w", encoding="utf-8") as handle:
        json.dump(optimized_list, handle, indent=2, ensure_ascii=False)

    print(f"Listo. {len(optimized_list)} videos preparados en {OUTPUT_DIR}.")


def main():
    parser = argparse.ArgumentParser(description="Transcodifica lotes de video para Instagram.")
    parser.add_argument("--limit", type=int, default=10)
    parser.add_argument("--source-file", default="pendientes_reels.json")
    args = parser.parse_args()
    transcode_batch(args.limit, args.source_file)


if __name__ == "__main__":
    main()
