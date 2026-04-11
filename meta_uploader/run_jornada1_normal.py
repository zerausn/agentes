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

from dotenv import load_dotenv

from meta_uploader import (
    diagnose_meta_connectivity,
    find_existing_facebook_video_by_caption_marker,
    find_existing_instagram_media_by_caption_marker,
    get_last_operation_status,
    upload_fb_reel,
    upload_fb_video_standard,
    upload_ig_feed_video_resumable,
    upload_ig_reel_resumable,
    upload_ig_story_video_resumable,
    ensure_ig_compatibility,
)


BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")
CALENDAR_FILE = BASE_DIR / "meta_calendar.json"
DATE_STEM_RE = re.compile(r"(?P<date>\d{8})_(?P<time>\d{6})")
__test__ = False
PUBLISHED_STATUSES = {
    "published",
    "published_with_ig_skip",
    "scheduled",
    "scheduled_with_ig_skip",
}
ACTIVE_STATUSES = {"in_progress", "running"}
WAITING_STATUSES = {"waiting_for_next_day", "daily_limit_reached"}
IG_REEL_FEED_MAX_BYTES = 300 * 1024 * 1024
IG_STORY_MAX_BYTES = 100 * 1024 * 1024
IG_MAX_WIDTH = 1920
IG_MIN_FPS = 23.0
IG_MAX_FPS = 60.0
IG_MAX_VIDEO_BITRATE_BPS = 25_000_000
IG_REEL_MAX_SECONDS = 15 * 60
IG_STORY_MAX_SECONDS = 60
IG_ALLOWED_VIDEO_CODECS = {"h264", "hevc"}


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


import time

def write_calendar(plan):
    temp_path = CALENDAR_FILE.with_suffix(f"{CALENDAR_FILE.suffix}.tmp")
    with open(temp_path, "w", encoding="utf-8") as handle:
        json.dump(plan, handle, indent=2, ensure_ascii=False)
    
    # Retry loop for Windows file locking
    for i in range(5):
        try:
            if CALENDAR_FILE.exists():
                os.remove(CALENDAR_FILE)
            os.replace(temp_path, CALENDAR_FILE)
            return
        except PermissionError:
            if i == 4: raise
            time.sleep(0.5)
        except Exception:
            if i == 4: raise
            time.sleep(0.5)


def load_existing_calendar():
    if not CALENDAR_FILE.exists():
        return None
    try:
        with open(CALENDAR_FILE, "r", encoding="utf-8") as handle:
            payload = json.load(handle)
        return payload if isinstance(payload, list) else None
    except Exception as exc:
        logging.warning("No se pudo leer %s para reanudar la jornada: %s", CALENDAR_FILE.name, exc)
        return None


def now_iso():
    return datetime.now().isoformat(timespec="seconds")


def _get_asset_path(asset):
    if not asset:
        return None
    if isinstance(asset, dict):
        return asset.get("path")
    if isinstance(asset, str):
        return asset
    return None


def build_day_signature(day_entry):
    return (
        day_entry.get("fecha"),
        _get_asset_path(day_entry.get("reel")),
        _get_asset_path(day_entry.get("post")),
    )


def build_asset_signature(day_entry):
    return (
        _get_asset_path(day_entry.get("reel")),
        _get_asset_path(day_entry.get("post")),
    )


def _copy_lane_runtime_metadata(new_lane, existing_lane):
    for field in ("attempt_count", "last_attempt_started_at", "last_attempt_finished_at"):
        if existing_lane.get(field) is not None:
            new_lane[field] = existing_lane[field]


def merge_existing_calendar(plan, existing_plan):
    existing_by_signature = {
        build_day_signature(day_entry): day_entry
        for day_entry in existing_plan
        if isinstance(day_entry, dict)
    }
    existing_by_assets = {
        build_asset_signature(day_entry): day_entry
        for day_entry in existing_plan
        if isinstance(day_entry, dict) and any(build_asset_signature(day_entry))
    }
    resumed_days = 0

    for day_entry in plan:
        existing_day = existing_by_signature.get(build_day_signature(day_entry))
        if not existing_day:
            existing_day = existing_by_assets.get(build_asset_signature(day_entry))
        if not existing_day:
            continue

        resumed_days += 1
        if existing_day.get("fecha"):
            day_entry["fecha"] = existing_day["fecha"]
        existing_summary = existing_day.get("summary") or {}
        if existing_summary.get("execution_order"):
            day_entry["summary"]["execution_order"] = existing_summary["execution_order"]

        for lane_name in ("reel", "post"):
            new_lane = day_entry.get(lane_name)
            existing_lane = (existing_day.get(lane_name) or {}) if isinstance(existing_day.get(lane_name), dict) else None
            if not new_lane or not existing_lane:
                continue
            if existing_lane.get("path") != new_lane.get("path"):
                continue

            existing_status = existing_lane.get("status")
            if existing_status in PUBLISHED_STATUSES:
                day_entry[lane_name] = existing_lane
                continue

            _copy_lane_runtime_metadata(new_lane, existing_lane)
            if existing_status == "in_progress":
                new_lane["status"] = "pending"
                new_lane["resume_note"] = "retry_after_unexpected_stop"
            elif existing_status:
                new_lane["status"] = existing_status

            if existing_lane.get("results") and existing_status == "failed":
                new_lane["results"] = existing_lane["results"]

        if existing_summary.get("status") == "completed":
            day_entry["summary"] = existing_summary
        elif existing_summary.get("status") == "paused_on_failure":
            day_entry["summary"] = existing_summary
        elif existing_summary.get("status") in ACTIVE_STATUSES:
            day_entry["summary"]["status"] = "pending"
            day_entry["summary"]["resume_note"] = "retry_after_unexpected_stop"

    if resumed_days:
        logging.info("Se reaplico estado previo de %s dia(s) desde %s.", resumed_days, CALENDAR_FILE.name)
    return plan


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
        "stream=width,height,duration,codec_name,avg_frame_rate,pix_fmt,bit_rate",
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
            "codec_name": (stream.get("codec_name") or "").lower(),
            "avg_frame_rate": stream.get("avg_frame_rate") or "0/0",
            "pix_fmt": stream.get("pix_fmt") or "",
            "bit_rate": int(stream.get("bit_rate") or 0),
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
            "codec_name": "",
            "avg_frame_rate": "0/0",
            "pix_fmt": "",
            "bit_rate": 0,
            "source_datetime": None,
        }


def parse_avg_frame_rate(value):
    if not value or value == "0/0":
        return 0.0
    if "/" in value:
        num, den = value.split("/", 1)
        try:
            denominator = float(den)
            if denominator == 0:
                return 0.0
            return float(num) / denominator
        except ValueError:
            return 0.0
    try:
        return float(value)
    except ValueError:
        return 0.0


def is_ig_story_safe(video_info):
    width = video_info.get("width", 0)
    height = video_info.get("height", 0)
    duration = video_info.get("duration_seconds", 0)
    if width <= 0 or height <= 0 or height <= width:
        return False
    return 3.0 <= duration <= 60.0


def evaluate_ig_video_preflight(video_info, lane_name):
    reasons = []
    duration = float(video_info.get("duration_seconds") or 0)
    size_bytes = int(video_info.get("size_bytes") or 0)
    width = int(video_info.get("width") or 0)
    fps = parse_avg_frame_rate(video_info.get("avg_frame_rate"))
    bitrate = int(video_info.get("bit_rate") or 0)
    codec = (video_info.get("codec_name") or "").lower()

    if lane_name == "story":
        max_bytes = IG_STORY_MAX_BYTES
        max_seconds = IG_STORY_MAX_SECONDS
    else:
        max_bytes = IG_REEL_FEED_MAX_BYTES
        max_seconds = IG_REEL_MAX_SECONDS

    if size_bytes > max_bytes:
        reasons.append(f"archivo {size_bytes / 1e6:.1f} MB > {max_bytes / 1e6:.0f} MB")
    if width > IG_MAX_WIDTH:
        reasons.append(f"ancho {width}px > {IG_MAX_WIDTH}px")
    if duration < 3.0 or duration > max_seconds:
        reasons.append(f"duracion {duration:.2f}s fuera de 3-{max_seconds}s")
    if fps and (fps < IG_MIN_FPS or fps > IG_MAX_FPS):
        reasons.append(f"fps {fps:.2f} fuera de {IG_MIN_FPS:.0f}-{IG_MAX_FPS:.0f}")
    if bitrate and bitrate > IG_MAX_VIDEO_BITRATE_BPS:
        reasons.append(f"bitrate {bitrate / 1e6:.2f} Mbps > {IG_MAX_VIDEO_BITRATE_BPS / 1e6:.0f} Mbps")
    if codec and codec not in IG_ALLOWED_VIDEO_CODECS:
        reasons.append(f"codec {codec} fuera de {sorted(IG_ALLOWED_VIDEO_CODECS)}")

    return {
        "compatible": not reasons,
        "reasons": reasons,
    }


def build_caption(video_info, lane, publish_date):
    stem = Path(video_info["path"]).stem
    return f"{stem} #PW"


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
    def _is_soft_skip(item):
        return item["status"].get("kind") == "skipped_requires_second_jornada"

    ok = all(item["result"] or _is_soft_skip(item) for item in platform_results.values())
    return ok, {
        key: {
            "result": value["result"],
            "status": value["status"],
        }
        for key, value in platform_results.items()
    }


def _build_skipped_result(label, kind, message):
    return {
        "label": label,
        "result": None,
        "status": {
            "kind": kind,
            "phase": "preflight",
            "message": message,
            "transient": False,
            "watchdog_alerted": False,
        },
    }


def _build_existing_remote_result(label, remote_item):
    result_id = str(remote_item.get("id") or "")
    remote_time = remote_item.get("created_time") or remote_item.get("timestamp") or "sin fecha"
    permalink = remote_item.get("permalink_url") or remote_item.get("permalink")
    message = f"ya existia remoto con id {result_id} ({remote_time})"
    if permalink:
        message = f"{message} | {permalink}"
    return {
        "label": label,
        "result": result_id,
        "status": {
            "kind": "already_exists_remote",
            "phase": "remote_guard",
            "message": message,
            "transient": False,
            "watchdog_alerted": False,
        },
    }


def _summary_has_second_jornada_skip(summary):
    return any(
        value.get("status", {}).get("kind") == "skipped_requires_second_jornada"
        for value in summary.values()
    )


def mark_lane_in_progress(day_entry, lane_name, video_info):
    lane_entry = day_entry[lane_name]
    lane_entry["status"] = "in_progress"
    lane_entry["attempt_count"] = int(lane_entry.get("attempt_count") or 0) + 1
    lane_entry["last_attempt_started_at"] = now_iso()
    lane_entry.pop("results", None)

    day_entry["summary"]["status"] = "running"
    day_entry["summary"]["active_lane"] = lane_name
    day_entry["summary"]["active_filename"] = video_info["filename"]
    day_entry["summary"]["last_updated_at"] = now_iso()


def clear_active_summary_fields(day_entry):
    day_entry["summary"].pop("active_lane", None)
    day_entry["summary"].pop("active_filename", None)


def mark_lane_finished(day_entry, lane_name, lane_status, summary):
    day_entry[lane_name].update(
        {
            "status": lane_status,
            "results": summary,
            "last_attempt_finished_at": now_iso(),
        }
    )
    day_entry["summary"]["last_updated_at"] = now_iso()
    clear_active_summary_fields(day_entry)


def run_platform_pair(lane_name, video_info, publish_date):
    # Horarios Gold Slots: 07:00 para Reels, 18:30 para Posts
    hour, minute = (7, 0) if lane_name == "reel" else (18, 30)
    scheduled_dt = datetime.strptime(publish_date, "%Y-%m-%d").replace(hour=hour, minute=minute)
    scheduled_timestamp = int(scheduled_dt.timestamp())

    caption = build_caption(video_info, lane_name, publish_date)
    platform_results = {}
    ig_label = "instagram_reel" if lane_name == "reel" else "instagram_feed"
    ig_preflight = evaluate_ig_video_preflight(video_info, lane_name)
    caption_marker = Path(video_info["path"]).stem
    fb_label = "facebook_reel" if lane_name == "reel" else "facebook_post"

    existing_facebook = find_existing_facebook_video_by_caption_marker(caption_marker)
    if existing_facebook:
        logging.warning(
            "Se detecto %s ya publicado en Facebook para %s con id %s. Se evita duplicado.",
            fb_label,
            video_info["filename"],
            existing_facebook["id"],
        )
        platform_results[fb_label] = _build_existing_remote_result(fb_label, existing_facebook)

    existing_instagram = None
    if ig_preflight["compatible"]:
        existing_instagram = find_existing_instagram_media_by_caption_marker(caption_marker)
        if existing_instagram:
            logging.warning(
                "Se detecto %s ya publicado en Instagram para %s con id %s. Se evita duplicado.",
                ig_label,
                video_info["filename"],
                existing_instagram["id"],
            )
            platform_results[ig_label] = _build_existing_remote_result(ig_label, existing_instagram)

    work = {}
    
    # --- LOGICA FACEBOOK DUAL ---
    if fb_label not in platform_results:
        # 1. Reel Inmediato (max 60s) para impacto viral
        logging.info("[%s] Generando Reel inmediato (60s) para Facebook...", fb_label.upper())
        fb_reel_path = ensure_ig_compatibility(video_info["path"], max_duration=60)
        work[f"{fb_label}_reel_now"] = (upload_fb_reel, fb_reel_path, caption)
        
        # 2. Video Completo Programado (Gold Slot)
        logging.info("[%s] Programando Video completo para %s @ %sh...", fb_label.upper(), publish_date, hour)
        work[f"{fb_label}_full_scheduled"] = (upload_fb_video_standard, video_info["path"], caption, scheduled_timestamp)

    # --- LOGICA INSTAGRAM ---
    if ig_preflight["compatible"] and ig_label not in platform_results:
        # Aplicamos Deep Clean para asegurar estabilidad en Instagram
        ig_path = ensure_ig_compatibility(video_info["path"], force_recode=True)
        work[ig_label] = (
            lambda path, text: upload_ig_reel_resumable(path, text, share_to_feed=False),
            ig_path,
            caption,
        )

    if not ig_preflight["compatible"]:
        reason_text = "; ".join(ig_preflight["reasons"])
        logging.warning(
            "Se omite %s para %s en jornada 1: el crudo no cumple specs oficiales de Instagram (%s). "
            "Se deriva a segunda jornada.",
            ig_label,
            video_info["filename"],
            reason_text,
        )
        platform_results[ig_label] = _build_skipped_result(
            ig_label,
            "skipped_requires_second_jornada",
            reason_text,
        )

    if work:
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


def execute_plan(plan, pause_between_assets=10, max_live_days=1):
    today = datetime.now().date()
    processed_live_days = 0

    for day_entry in plan:
        publish_date = day_entry["fecha"]
        publish_day = datetime.strptime(publish_date, "%Y-%m-%d").date()
        if day_entry["summary"].get("status") == "completed":
            logging.info("Se conserva %s como completado desde el calendario existente.", publish_date)
            continue
        if day_entry["summary"].get("status") == "paused_on_failure":
            logging.error(
                "La jornada sigue pausada por un fallo previo en %s. Revisa meta_calendar.json antes de continuar.",
                publish_date,
            )
            return False, "paused_on_failure"
        # Eliminamos el bloqueo de futuro para permitir programacion masiva (Wraparound 29 dias)
        if (publish_day - today).days > 29:
            logging.info(
                "Se detiene en %s porque supera el limite maximo de programacion de Meta (29 dias).",
                publish_date,
            )
            return True, "max_future_reached"
        if max_live_days is not None and processed_live_days >= max_live_days:
            logging.info(
                "Se completo el cupo de %s dia(s) en esta corrida. Se detiene para respetar 1 publicacion por dia real.",
                max_live_days,
            )
            return True, "daily_limit_reached"

        tasks = []
        if day_entry["reel"]:
            tasks.append(("reel", day_entry["reel"]))
        if day_entry["post"]:
            tasks.append(("post", day_entry["post"]))
        tasks.sort(key=lambda item: item[1]["size_bytes"], reverse=True)
        day_entry["summary"]["execution_order"] = [lane for lane, _ in tasks]
        if not day_entry["summary"].get("status"):
            day_entry["summary"]["status"] = "pending"

        logging.info("======== Jornada 1 | %s ========", publish_date)
        logging.info("Orden del dia: %s", ", ".join(day_entry["summary"]["execution_order"]) or "sin assets")

        for lane_name, video_info in tasks:
            if day_entry[lane_name].get("status") in PUBLISHED_STATUSES:
                logging.info(
                    "[%s] %s ya estaba marcado como %s. Se conserva y se continua.",
                    lane_name.upper(),
                    video_info["filename"],
                    day_entry[lane_name]["status"],
                )
                continue

            logging.info(
                "[%s] %s | %.2f MB | %.2fs",
                lane_name.upper(),
                video_info["filename"],
                video_info["size_bytes"] / 1e6,
                video_info["duration_seconds"],
            )
            mark_lane_in_progress(day_entry, lane_name, video_info)
            write_calendar(plan)
            ok, summary = run_platform_pair(lane_name, video_info, publish_date)
            lane_status = (
                "published_with_ig_skip"
                if ok and _summary_has_second_jornada_skip(summary)
                else "published"
                if ok
                else "failed"
            )
            mark_lane_finished(day_entry, lane_name, lane_status, summary)
            write_calendar(plan)

            # --- MONITOR SENTINEL: REPORTE DE ALTA VISIBILIDAD ---
            if ok:
                target_info = "Publicado AHORA"
                # Intentamos extraer el timestamp de programación si existe
                for res in summary.values():
                    sch = res.get("scheduled") or res.get("status", {}).get("message")
                    if isinstance(sch, dict) and sch.get("scheduled_local"):
                        target_info = f"Programado: {sch['scheduled_local']}"
                        break
                    elif isinstance(sch, str) and " -> " in sch:
                        # Formato legacy de algunos status messages
                        target_info = f"Programado: {sch.split(' -> ')[1]}"
                        break
                
                print(f"\n[MONITOR] \033[92mÚLTIMA SUBIDA EXITOSA\033[0m: {video_info['filename']} -> {target_info}\n")
            
            if not ok:
                day_entry["summary"]["status"] = "paused_on_failure"
                day_entry["summary"]["last_updated_at"] = now_iso()
                write_calendar(plan)
                logging.error(
                    "Se pausa la jornada 1 en %s para no quemar cola. Revisa meta_uploader.log y meta_calendar.json.",
                    video_info["filename"],
                )
                return False, "paused_on_failure"
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
        day_entry["summary"]["last_updated_at"] = now_iso()
        clear_active_summary_fields(day_entry)
        write_calendar(plan)
        processed_live_days += 1
        if max_live_days is not None and processed_live_days >= max_live_days:
            logging.info(
                "Se completo %s y se frena la corrida para respetar la regla de una publicacion por dia real.",
                publish_date,
            )
            return True, "daily_limit_reached"

    return True, "completed"


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
        "--max-live-days",
        type=int,
        default=29,
        help="Maximo de dias reales a ejecutar por corrida (Programacion Masiva Segura - Limite 29 dias).",
    )
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
    parser.add_argument(
        "--rebuild-plan",
        action="store_true",
        help="Ignora el calendario existente y reconstruye el plan desde las colas actuales.",
    )
    args = parser.parse_args()

    try:
        if not require_upload_opt_in():
            return 1

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
        if not args.rebuild_plan:
            existing_plan = load_existing_calendar()
            if existing_plan:
                plan = merge_existing_calendar(plan, existing_plan)

        write_calendar(plan)
        logging.info("Calendario operativo guardado en %s con %s dias.", CALENDAR_FILE.name, len(plan))

        if args.plan_only:
            return 0

        ok, reason = execute_plan(
            plan,
            pause_between_assets=args.pause_between_assets,
            max_live_days=args.max_live_days,
        )
        if ok:
            if reason in WAITING_STATUSES:
                logging.info(
                    "Jornada 1 queda en espera del siguiente dia operativo. Motivo: %s.",
                    reason,
                )
            else:
                logging.info("Jornada 1 completada segun el calendario operativo.")
            return 0
        return 2
    except KeyboardInterrupt:
        logging.warning("Jornada 1 interrumpida manualmente.")
        return 130
    except Exception:
        logging.exception("Fallo fatal no controlado en el runner normal de jornada 1.")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
