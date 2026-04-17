import argparse
import json
import logging
import os
import subprocess
import time
from pathlib import Path

from meta_uploader import (
    get_last_operation_status,
    upload_fb_reel,
    upload_fb_video_standard,
    upload_ig_reel_resumable,
)


BASE_DIR = Path(__file__).resolve().parent
__test__ = False


logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(message)s")


def get_duration(path):
    cmd = ["ffprobe", "-v", "error", "-show_entries", "stream=duration", "-of", "json", path]
    try:
        response = subprocess.check_output(cmd).decode()
        data = json.loads(response)
        return float(data["streams"][0]["duration"])
    except Exception:
        return 0


def require_upload_opt_in():
    if os.environ.get("META_ENABLE_UPLOAD") == "1":
        return True
    logging.error("Este script publica de verdad. Exporta META_ENABLE_UPLOAD=1 para habilitarlo.")
    return False


def load_queue(source):
    queue_path = BASE_DIR / f"pendientes_{source}.json"
    with open(queue_path, "r", encoding="utf-8") as handle:
        return json.load(handle)


def build_caption(video_path):
    return f"Subida automatizada: {Path(video_path).stem}"


def run_test_batch(limit=10, start_index=0, source="reels", max_retries_per_asset=2, retry_sleep_seconds=15):
    if not require_upload_opt_in():
        return

    try:
        videos = load_queue(source)
    except FileNotFoundError:
        logging.error("No se encontro la cola pendientes_%s.json.", source)
        return

    batch = videos[start_index : start_index + limit]
    logging.info("Iniciando batch manual sobre %s videos de la cola %s.", len(batch), source)

    for offset, video_path in enumerate(batch, start=start_index + 1):
        filename = os.path.basename(video_path)
        caption = build_caption(video_path)
        duration = get_duration(video_path)
        logging.info("--- [%s] %s ---", offset, filename)

        fb_result = None
        ig_result = None
        last_status = {}

        for attempt in range(1, max_retries_per_asset + 1):
            if source == "reels" and duration <= 90:
                fb_result = upload_fb_reel(video_path, caption)
                ig_result = upload_ig_reel_resumable(video_path, caption)
            else:
                fb_result = upload_fb_video_standard(video_path, caption)
                logging.info(
                    "La cola %s se trata como carril de post/video. IG no se intenta desde este script.",
                    source,
                )

            last_status = get_last_operation_status()
            if fb_result or not last_status.get("transient"):
                break

            if attempt >= max_retries_per_asset:
                logging.error(
                    "Fallo transitorio agotando %s reintentos para %s. Se pausa el batch para no quemar cola. Estado: %s",
                    max_retries_per_asset,
                    filename,
                    last_status,
                )
                return

            logging.warning(
                "Fallo transitorio en %s (intento %s/%s). Se reintentara el mismo asset en %ss. Estado: %s",
                filename,
                attempt,
                max_retries_per_asset,
                retry_sleep_seconds,
                last_status,
            )
            time.sleep(retry_sleep_seconds)

        logging.info("Resultado %s | FB=%s | IG=%s", filename, fb_result, ig_result)
        time.sleep(10)


def main():
    parser = argparse.ArgumentParser(description="Ejecuta un batch manual de subida contra Meta.")
    parser.add_argument("--limit", type=int, default=10)
    parser.add_argument("--start-index", type=int, default=0)
    parser.add_argument("--source", choices=["reels", "posts"], default="reels")
    parser.add_argument("--max-retries-per-asset", type=int, default=2)
    parser.add_argument("--retry-sleep-seconds", type=int, default=15)
    args = parser.parse_args()
    run_test_batch(args.limit, args.start_index, args.source, args.max_retries_per_asset, args.retry_sleep_seconds)


if __name__ == "__main__":
    main()
