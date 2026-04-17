import argparse
import concurrent.futures
import json
import logging
import os
import subprocess
import time
from pathlib import Path

from meta_uploader import upload_fb_file_handle, upload_fb_reel, upload_ig_reel_resumable


BASE_DIR = Path(__file__).resolve().parent
OPTIMIZED_DIR = BASE_DIR / "optimized_videos"
__test__ = False


logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(message)s")


def require_upload_opt_in():
    if os.environ.get("META_ENABLE_UPLOAD") == "1":
        return True
    logging.error("Este script publica de verdad. Exporta META_ENABLE_UPLOAD=1 para habilitarlo.")
    return False


def load_reel_queue():
    with open(BASE_DIR / "pendientes_reels.json", "r", encoding="utf-8") as handle:
        return json.load(handle)


def ensure_instagram_optimized_copy(video_path):
    OPTIMIZED_DIR.mkdir(exist_ok=True)
    source_path = Path(video_path)
    output_path = OPTIMIZED_DIR / f"opt_{source_path.name}"

    if output_path.exists() and output_path.stat().st_size > 0:
        return output_path
    if output_path.exists():
        logging.warning("Se detecto una copia optimizada vacia o corrupta; se regenerara %s", output_path.name)
        output_path.unlink()

    logging.info("Transcodificando copia para Instagram: %s", source_path.name)
    cmd = [
        "ffmpeg",
        "-y",
        "-i",
        str(source_path),
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
        str(output_path),
    ]
    subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return output_path


def task_facebook(video_path, caption, facebook_mode):
    logging.info("[FACEBOOK] Iniciando %s para %s", facebook_mode, Path(video_path).name)
    if facebook_mode == "file_handle":
        return upload_fb_file_handle(video_path, caption)
    return upload_fb_reel(video_path, caption)


def task_instagram(video_path, caption):
    optimized_path = ensure_instagram_optimized_copy(video_path)
    logging.info("[INSTAGRAM] Iniciando subida optimizada para %s", optimized_path.name)
    return upload_ig_reel_resumable(str(optimized_path), caption)


def run_dual_batch(limit=10, start_index=0, facebook_mode="reel"):
    if not require_upload_opt_in():
        return

    try:
        videos = load_reel_queue()
    except FileNotFoundError:
        logging.error("No se encontro pendientes_reels.json.")
        return

    batch = videos[start_index : start_index + limit]
    logging.info("Iniciando batch paralelo sobre %s reels.", len(batch))

    for offset, video_path in enumerate(batch, start=start_index + 1):
        filename = os.path.basename(video_path)
        caption = f"Subida automatizada paralela: {Path(video_path).stem}"
        logging.info("==========================================")
        logging.info("--- [%s] %s ---", offset, filename)
        logging.info("==========================================")

        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
            future_fb = executor.submit(task_facebook, video_path, caption, facebook_mode)
            future_ig = executor.submit(task_instagram, video_path, caption)
            fb_result = future_fb.result()
            ig_result = future_ig.result()

        logging.info("Resultado %s | FB=%s | IG=%s", filename, fb_result, ig_result)
        time.sleep(10)


def main():
    parser = argparse.ArgumentParser(description="Batch paralelo para el carril compartido FB Reel + IG Reel.")
    parser.add_argument("--limit", type=int, default=10)
    parser.add_argument("--start-index", type=int, default=0)
    parser.add_argument("--facebook-mode", choices=["reel", "file_handle"], default="reel")
    args = parser.parse_args()
    run_dual_batch(args.limit, args.start_index, args.facebook_mode)


if __name__ == "__main__":
    main()
