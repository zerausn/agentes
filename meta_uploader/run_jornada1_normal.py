import argparse
import concurrent.futures
import json
import logging
import os
import re
import subprocess
import time
from datetime import datetime, timedelta
from pathlib import Path

from meta_uploader import (
    diagnose_meta_connectivity,
    get_last_operation_status,
    upload_fb_reel,
    upload_fb_video_standard,
    upload_ig_feed_video_resumable,
    upload_ig_reel_resumable,
    upload_ig_story_video_resumable,
)


BASE_DIR = Path(__file__).resolve().parent
CALENDAR_FILE = BASE_DIR / "meta_calendar.json"
DATE_STEM_RE = re.compile(r"(?P<date>\d{8})_(?P<time>\d{6})")
__test__ = False


logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(message)s")


def require_upload_opt_in():
    if os.environ.get("META_ENABLE_UPLOAD") == "1":
        return True
    logging.error("Este script publica de verdad. Exporta META_ENABLE_UPLOAD=1 para habilitarlo.")
    return False


def load_queue(name):
    queue_path = BASE_DIR / f"pendientes_{name}.json"
    try:
        with open(queue_path, "r", encoding="utf-8") as handle:
            return json.load(handle)
    except FileNotFoundError:
        logging.warning("No se encontro %s.", queue_path.name)
        return []


def write_calendar(plan):
    with open(CALENDAR_FILE, "w", encoding="utf-8") as handle:
        json.dump(plan, handle, indent=2, ensure_ascii=False)


def parse_source_datetime(video_path):
    match = DATE_STEM_RE.search(Path(video_path).stem)
    if not match:
        return None
    try:
        return datetime.strptime(f"{match.group('date')}_{match.group('time')}", "%Y%m%d_%H%M%S")
    except ValueError:
        return None


def probe_video(video_path):
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
        video_path,
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        data = json.loads(result.stdout)
        stream = (data.get("streams") or [{}])[0]
        source_dt = parse_source_datetime(video_path)
        return {
            "path": video_path,
            "filename": Path(video_path).name,
            "size_bytes": Path(video_path).stat().st_size,
            "duration_seconds": float(stream.get("duration") or 0),
            "width": int(stream.get("width") or 0),
            "height": int(stream.get("height") or 0),
            "source_datetime": source_dt.isoformat() if source_dt else None,
        }
    except Exception as exc:
        logging.error("No se pudo inspeccionar %s: %s", video_path, exc)
        return {
            "path": video_path,
            "filename": Path(video_path).name,
            "size_bytes": Path(video_path).stat().st_size if Path(video_path).exists() else 0,
            "duration_seconds": 0,
            "width": 0,
            "height": 0,
            "source_datetime": None,
        }


def is_ig_story_safe(video_info):
    width = video_info.get("width", 0)
    height = video_info.get("height", 0)
    duration = video_info.get("duration_seconds", 0)
    if width <= 0 or height <= 0 or height <= width:
        return False
    return 3.0 <= duration <= 60.0


def build_caption(video_info, lane, publish_date):
    stem = Path(video_info["path"]).stem
    return f"PW | {publish_date} | {stem}"


def build_plan(reels, posts, *, reel_start_index, post_start_index, days, start_date, enable_ig_stories):
    base_date = datetime.strptime(start_date, "%Y-%m-%d").date() if start_date else datetime.now().date()
    max_available = max(len(reels) - reel_start_index, len(posts) - post_start_index, 0)
    if days is None:
        max_days = max_available
    else:
        max_days = min(days, max_available)
    plan = []

    for day_offset in range(max_days):
        publish_date = (base_date + timedelta(days=day_offset)).isoformat()
        reel_path = reels[reel_start_index + day_offset] if reel_start_index + day_offset < len(reels) else None
        post_path = posts[post_start_index + day_offset] if post_start_index + day_offset < len(posts) else None

        reel_info = probe_video(reel_path) if reel_path else None
        post_info = probe_video(post_path) if post_path else None
        ig_story_enabled = bool(enable_ig_stories and reel_info and is_ig_story_safe(reel_info))

        day_entry = {
            "fecha": publish_date,
            "reel": {
                "path": reel_info["path"],
                "filename": reel_info["filename"],
                "size_bytes": reel_info["size_bytes"],
                "duration_seconds": reel_info["duration_seconds"],
                "source_datetime": reel_info["source_datetime"],
                "routes": ["facebook_reel", "instagram_reel"],
                "status": "pending",
            }
            if reel_info
            else None,
            "post": {
                "path": post_info["path"],
                "filename": post_info["filename"],
                "size_bytes": post_info["size_bytes"],
                "duration_seconds": post_info["duration_seconds"],
                "source_datetime": post_info["source_datetime"],
                "routes": ["facebook_post", "instagram_feed"],
                "status": "pending",
            }
            if post_info
            else None,
            "instagram_story": {
                "enabled": ig_story_enabled,
                "path": reel_info["path"] if ig_story_enabled else None,
                "status": "pending" if ig_story_enabled else "skipped_not_story_safe",
            },
            "facebook_story": {
                "enabled": False,
                "status": "skipped_unsupported",
                "reason": "Facebook Stories sigue fuera del flujo automatizado actual por soporte oficial no versionado.",
            },
            "summary": {
                "status": "pending",
                "execution_order": [],
            },
        }
        plan.append(day_entry)

    return plan


def _invoke_with_status(label, func, *args):
    try:
        result = func(*args)
    except Exception as exc:
        logging.exception("Fallo inesperado en %s: %s", label, exc)
        result = None
    return {
        "label": label,
        "result": result,
        "status": get_last_operation_status(),
    }


def _summarize_platform_results(platform_results):
    ok = all(item["result"] for item in platform_results.values())
    return ok, {
        key: {
            "result": value["result"],
            "status": value["status"],
        }
        for key, value in platform_results.items()
    }


def run_platform_pair(lane_name, video_info, publish_date):
    caption = build_caption(video_info, lane_name, publish_date)
    if lane_name == "reel":
        work = {
            "facebook_reel": (upload_fb_reel, video_info["path"], caption),
            "instagram_reel": (lambda path, text: upload_ig_reel_resumable(path, text, share_to_feed=False), video_info["path"], caption),
        }
    else:
        work = {
            "facebook_post": (upload_fb_video_standard, video_info["path"], caption),
            "instagram_feed": (upload_ig_feed_video_resumable, video_info["path"], caption),
        }

    platform_results = {}
    with concurrent.futures.ThreadPoolExecutor(max_workers=len(work)) as executor:
        future_map = {
            executor.submit(_invoke_with_status, label, fn, *args): label
            for label, (fn, *args) in work.items()
        }
        for future in concurrent.futures.as_completed(future_map):
            label = future_map[future]
            platform_results[label] = future.result()

    ok, summary = _summarize_platform_results(platform_results)
    if not ok:
        diagnostics = diagnose_meta_connectivity()
        logging.error(
            "Fallo la dupla %s para %s. Diagnostico red/Meta: %s",
            lane_name,
            video_info["filename"],
            diagnostics["summary"],
        )
    return ok, summary


def run_ig_story_if_enabled(day_entry):
    story = day_entry["instagram_story"]
    if not story["enabled"] or not story["path"]:
        return story

    result = upload_ig_story_video_resumable(story["path"])
    status = get_last_operation_status()
    story.update(
        {
            "result": result,
            "status": "published" if result else "failed",
            "operation_status": status,
        }
    )
    return story


def execute_plan(plan, pause_between_assets=10):
    for day_entry in plan:
        publish_date = day_entry["fecha"]
        tasks = []
        if day_entry["reel"]:
            tasks.append(("reel", day_entry["reel"]))
        if day_entry["post"]:
            tasks.append(("post", day_entry["post"]))
        tasks.sort(key=lambda item: item[1]["size_bytes"], reverse=True)
        day_entry["summary"]["execution_order"] = [lane for lane, _ in tasks]

        logging.info("======== Jornada 1 | %s ========", publish_date)
        logging.info("Orden del dia: %s", ", ".join(day_entry["summary"]["execution_order"]) or "sin assets")

        for lane_name, video_info in tasks:
            logging.info(
                "[%s] %s | %.2f MB | %.2fs",
                lane_name.upper(),
                video_info["filename"],
                video_info["size_bytes"] / 1e6,
                video_info["duration_seconds"],
            )
            ok, summary = run_platform_pair(lane_name, video_info, publish_date)
            day_entry[lane_name].update(
                {
                    "status": "published" if ok else "failed",
                    "results": summary,
                }
            )
            write_calendar(plan)
            if not ok:
                day_entry["summary"]["status"] = "paused_on_failure"
                write_calendar(plan)
                logging.error(
                    "Se pausa la jornada 1 en %s para no quemar cola. Revisa meta_uploader.log y meta_calendar.json.",
                    video_info["filename"],
                )
                return False
            time.sleep(pause_between_assets)

            if lane_name == "reel":
                story_state = run_ig_story_if_enabled(day_entry)
                write_calendar(plan)
                if story_state["status"] == "failed":
                    logging.warning(
                        "IG Story no paso con %s. Se registra como fallo suave y la jornada continua.",
                        Path(story_state["path"]).name,
                    )

        day_entry["summary"]["status"] = "completed"
        write_calendar(plan)

    return True


def main():
    parser = argparse.ArgumentParser(
        description="Runner normal de jornada 1 para videos crudos en Facebook e Instagram."
    )
    parser.add_argument("--days", type=int, default=7, help="Cantidad de dias a planificar/ejecutar.")
    parser.add_argument("--start-date", default=None, help="Fecha inicial YYYY-MM-DD. Default: hoy.")
    parser.add_argument("--reel-start-index", type=int, default=0)
    parser.add_argument("--post-start-index", type=int, default=0)
    parser.add_argument("--pause-between-assets", type=int, default=10)
    parser.add_argument(
        "--disable-ig-stories",
        action="store_true",
        help="Desactiva el intento best-effort de IG Story sobre el reel vertical del dia.",
    )
    parser.add_argument(
        "--plan-only",
        action="store_true",
        help="Solo genera meta_calendar.json sin ejecutar subidas.",
    )
    args = parser.parse_args()

    if not require_upload_opt_in():
        return

    reels = load_queue("reels")
    posts = load_queue("posts")
    plan = build_plan(
        reels,
        posts,
        reel_start_index=args.reel_start_index,
        post_start_index=args.post_start_index,
        days=args.days,
        start_date=args.start_date,
        enable_ig_stories=not args.disable_ig_stories,
    )
    write_calendar(plan)
    logging.info("Calendario operativo guardado en %s con %s dias.", CALENDAR_FILE.name, len(plan))

    if args.plan_only:
        return

    ok = execute_plan(plan, pause_between_assets=args.pause_between_assets)
    if ok:
        logging.info("Jornada 1 completada segun el calendario operativo.")


if __name__ == "__main__":
    main()
