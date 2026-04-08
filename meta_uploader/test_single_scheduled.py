"""
Sonda manual de un solo asset para validar, con opt-in explicito, que formatos
siguen funcionando de verdad contra Meta antes de escalar a una corrida por
dias. Mantiene el nombre heredado del archivo para no romper referencias
locales, pero hoy ya no agenda nada: prueba un activo pesado, deriva un clip
vertical corto para stories/reels y deja evidencia estructurada en JSON.
"""

import json
import logging
import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path

from meta_uploader import (
    upload_fb_reel,
    upload_fb_video_standard,
    upload_ig_feed_video_resumable,
    upload_ig_reel_resumable,
    upload_ig_story_video_resumable,
)
from test_batch_upload_v2 import ensure_instagram_optimized_copy


BASE_DIR = Path(__file__).resolve().parent
OPTIMIZED_DIR = BASE_DIR / "optimized_videos"
RESULT_FILE = BASE_DIR / "single_format_probe_result.json"
QUEUE_REELS = BASE_DIR / "pendientes_reels.json"
QUEUE_POSTS = BASE_DIR / "pendientes_posts.json"
__test__ = False


logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(message)s")


def require_upload_opt_in():
    if os.environ.get("META_ENABLE_UPLOAD") == "1":
        return True
    logging.error("Este script publica de verdad. Exporta META_ENABLE_UPLOAD=1 para habilitarlo.")
    return False


def load_queue(queue_path):
    try:
        with open(queue_path, "r", encoding="utf-8") as handle:
            return json.load(handle)
    except FileNotFoundError:
        return []


def inspect_video(video_path):
    cmd = [
        "ffprobe",
        "-v",
        "error",
        "-select_streams",
        "v:0",
        "-show_entries",
        "stream=width,height,r_frame_rate,duration,codec_name",
        "-of",
        "json",
        str(video_path),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, check=True)
    payload = json.loads(result.stdout)
    stream = (payload.get("streams") or [None])[0] or {}
    return {
        "codec_name": stream.get("codec_name"),
        "width": int(stream.get("width") or 0),
        "height": int(stream.get("height") or 0),
        "duration": float(stream.get("duration") or 0),
        "r_frame_rate": stream.get("r_frame_rate"),
    }


def is_reel_safe(meta):
    width = meta.get("width", 0)
    height = meta.get("height", 0)
    duration = meta.get("duration", 0.0)
    if width <= 0 or height <= 0 or height <= width:
        return False
    if not (3.0 <= duration <= 90.0):
        return False
    ratio = width / height
    return abs(ratio - (9 / 16)) <= 0.08


def is_story_safe(meta, size_bytes):
    width = meta.get("width", 0)
    height = meta.get("height", 0)
    duration = meta.get("duration", 0.0)
    if width <= 0 or height <= 0:
        return False
    if not (3.0 <= duration <= 60.0):
        return False
    if size_bytes > 100 * 1024 * 1024:
        return False
    return True


def load_ranked_assets(queue_path):
    ranked = []
    for raw_path in load_queue(queue_path):
        path = Path(raw_path)
        if not path.exists():
            continue
        ranked.append(
            {
                "path": str(path),
                "name": path.name,
                "size_bytes": path.stat().st_size,
            }
        )
    ranked.sort(key=lambda item: item["size_bytes"], reverse=True)
    return ranked


def build_caption(video_name, channel):
    return f"Prueba automatizada {channel}: {Path(video_name).stem}"


def ensure_vertical_probe_copy(video_path, source_meta):
    OPTIMIZED_DIR.mkdir(exist_ok=True)
    source_path = Path(video_path)
    output_path = OPTIMIZED_DIR / f"probe_vertical_{source_path.stem}.mp4"

    if output_path.exists() and output_path.stat().st_size > 0:
        return output_path

    target_duration = max(3.0, min(source_meta.get("duration", 30.0), 30.0))
    cmd = [
        "ffmpeg",
        "-y",
        "-ss",
        "0",
        "-t",
        f"{target_duration:.3f}",
        "-i",
        str(source_path),
        "-vf",
        "fps=30,scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,format=yuv420p",
        "-c:v",
        "libx264",
        "-preset",
        "veryfast",
        "-crf",
        "23",
        "-movflags",
        "+faststart",
        "-c:a",
        "aac",
        "-b:a",
        "128k",
        str(output_path),
    ]
    logging.info("Derivando clip vertical de prueba desde %s", source_path.name)
    subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return output_path


def write_result(payload):
    with open(RESULT_FILE, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, ensure_ascii=False)


def mark_skip(reason, detail):
    return {"status": "skipped", "reason": reason, "detail": detail}


def execute_step(label, fn):
    logging.info("Ejecutando %s...", label)
    try:
        result = fn()
    except Exception as exc:
        logging.exception("%s lanzo una excepcion.", label)
        return {"status": "error", "detail": str(exc)}

    if result:
        return {"status": "success", "result": str(result)}
    return {"status": "failed", "detail": "Meta no devolvio un identificador de confirmacion."}


def main():
    if not require_upload_opt_in():
        return

    reels = load_ranked_assets(QUEUE_REELS)
    posts = load_ranked_assets(QUEUE_POSTS)

    primary_asset = reels[0] if reels else (posts[0] if posts else None)
    if not primary_asset:
        logging.error("No hay videos disponibles en pendientes_reels.json ni pendientes_posts.json.")
        return

    primary_meta = inspect_video(primary_asset["path"])
    primary_asset["size_mb"] = round(primary_asset["size_bytes"] / (1024 * 1024), 1)
    primary_asset["video"] = primary_meta
    primary_asset["queue"] = "reels" if reels else "posts"
    primary_asset["reel_safe"] = is_reel_safe(primary_meta)

    logging.info("Video seleccionado: %s", primary_asset["name"])
    logging.info(
        "Cola=%s | %.1f MB | %ss | %sx%s",
        primary_asset["queue"],
        primary_asset["size_mb"],
        round(primary_meta["duration"], 3),
        primary_meta["width"],
        primary_meta["height"],
    )

    optimized_post_path = ensure_instagram_optimized_copy(primary_asset["path"])
    probe_source = reels[0] if reels else primary_asset
    probe_source_meta = inspect_video(probe_source["path"])
    vertical_probe_path = ensure_vertical_probe_copy(probe_source["path"], probe_source_meta)
    vertical_probe_meta = inspect_video(vertical_probe_path)
    vertical_probe_size_bytes = vertical_probe_path.stat().st_size
    vertical_probe_size_mb = round(vertical_probe_size_bytes / (1024 * 1024), 1)

    probe = {
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "result_file": str(RESULT_FILE),
        "asset": {
            "path": primary_asset["path"],
            "name": primary_asset["name"],
            "queue": primary_asset["queue"],
            "size_mb": primary_asset["size_mb"],
            "reel_safe": primary_asset["reel_safe"],
            "optimized_path": str(optimized_post_path),
            "video": primary_meta,
        },
        "vertical_probe_asset": {
            "source_path": probe_source["path"],
            "source_name": probe_source["name"],
            "generated_from_queue": "reels" if reels else "posts",
            "path": str(vertical_probe_path),
            "size_mb": vertical_probe_size_mb,
            "reel_safe": is_reel_safe(vertical_probe_meta),
            "story_safe": is_story_safe(vertical_probe_meta, vertical_probe_size_bytes),
            "video": vertical_probe_meta,
        },
        "formats": {
            "facebook_story": mark_skip(
                "no_official_page_story_flow_confirmed",
                "No se encontro una guia oficial equivalente para publicar Stories de Facebook Pages en el flujo versionado en este repo.",
            ),
        },
    }

    if probe["vertical_probe_asset"]["story_safe"]:
        probe["formats"]["instagram_story"] = execute_step(
            "Instagram Story",
            lambda: upload_ig_story_video_resumable(str(vertical_probe_path)),
        )
    else:
        probe["formats"]["instagram_story"] = mark_skip(
            "derived_probe_not_story_safe",
            "El clip derivado no quedo dentro de las restricciones oficiales de Story para tamano/duracion.",
        )

    if probe["vertical_probe_asset"]["reel_safe"]:
        probe["formats"]["instagram_reel"] = execute_step(
            "Instagram Reel",
            lambda: upload_ig_reel_resumable(
                str(vertical_probe_path),
                build_caption(vertical_probe_path.name, "IG reel"),
                share_to_feed=False,
            ),
        )
        probe["formats"]["facebook_reel"] = execute_step(
            "Facebook Reel",
            lambda: upload_fb_reel(str(vertical_probe_path), build_caption(vertical_probe_path.name, "FB reel")),
        )
    else:
        probe["formats"]["instagram_reel"] = mark_skip(
            "derived_probe_not_reel_safe",
            "El clip derivado no quedo dentro del subconjunto seguro compartido para reels.",
        )
        probe["formats"]["facebook_reel"] = mark_skip(
            "derived_probe_not_reel_safe",
            "El clip derivado no quedo dentro del subconjunto seguro compartido para reels.",
        )

    if primary_asset["reel_safe"]:
        probe["formats"]["instagram_post"] = execute_step(
            "Instagram video compartido al feed",
            lambda: upload_ig_feed_video_resumable(
                str(optimized_post_path),
                build_caption(primary_asset["name"], "IG post"),
            ),
        )
    else:
        probe["formats"]["instagram_post"] = execute_step(
            "Instagram video compartido al feed",
            lambda: upload_ig_feed_video_resumable(
                str(optimized_post_path),
                build_caption(primary_asset["name"], "IG post"),
            ),
        )

    probe["formats"]["facebook_post"] = execute_step(
        "Facebook video post",
        lambda: upload_fb_video_standard(
            primary_asset["path"],
            build_caption(primary_asset["name"], "FB post"),
        ),
    )

    write_result(probe)
    logging.info("Resultado estructurado guardado en %s", RESULT_FILE.name)
    logging.info(json.dumps(probe, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
