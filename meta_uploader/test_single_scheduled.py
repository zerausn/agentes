"""
Sonda manual de un solo asset para validar, con opt-in explicito, que formatos
siguen funcionando de verdad contra Meta antes de escalar a una corrida por
dias. Mantiene el nombre heredado del archivo para no romper referencias
locales, pero hoy ya no agenda nada: prueba un activo pesado y deja evidencia
estructurada en JSON.
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
)
from test_batch_upload_v2 import ensure_instagram_optimized_copy


BASE_DIR = Path(__file__).resolve().parent
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

    optimized_path = ensure_instagram_optimized_copy(primary_asset["path"])

    probe = {
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "result_file": str(RESULT_FILE),
        "asset": {
            "path": primary_asset["path"],
            "name": primary_asset["name"],
            "queue": primary_asset["queue"],
            "size_mb": primary_asset["size_mb"],
            "reel_safe": primary_asset["reel_safe"],
            "optimized_path": str(optimized_path),
            "video": primary_meta,
        },
        "formats": {
            "instagram_story": mark_skip(
                "unsupported_by_current_official_docs",
                "La documentacion oficial versionada en este repo no cubre publicacion de Stories por API para este flujo.",
            ),
            "facebook_story": mark_skip(
                "unsupported_by_current_official_docs",
                "La documentacion oficial versionada en este repo no cubre publicacion de Stories por API para este flujo.",
            ),
        },
    }

    if primary_asset["reel_safe"]:
        caption_ig = build_caption(primary_asset["name"], "IG reel+feed")
        probe["formats"]["instagram_reel"] = execute_step(
            "Instagram Reel compartido al feed",
            lambda: upload_ig_feed_video_resumable(str(optimized_path), caption_ig),
        )
        probe["formats"]["instagram_post"] = {
            "status": probe["formats"]["instagram_reel"]["status"],
            "detail": "Se cubre con la misma publicacion porque el flujo usa REELS con share_to_feed=true.",
            "result": probe["formats"]["instagram_reel"].get("result"),
        }
        probe["formats"]["facebook_reel"] = execute_step(
            "Facebook Reel",
            lambda: upload_fb_reel(primary_asset["path"], build_caption(primary_asset["name"], "FB reel")),
        )
    else:
        probe["formats"]["instagram_reel"] = mark_skip(
            "no_reel_compatible_asset",
            "No hay video clasificado como reel seguro en pendientes_reels.json; la cola actual esta vacia.",
        )
        probe["formats"]["facebook_reel"] = mark_skip(
            "no_reel_compatible_asset",
            "No hay video clasificado como reel seguro en pendientes_reels.json; la cola actual esta vacia.",
        )
        probe["formats"]["instagram_post"] = execute_step(
            "Instagram video compartido al feed",
            lambda: upload_ig_feed_video_resumable(
                str(optimized_path),
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
