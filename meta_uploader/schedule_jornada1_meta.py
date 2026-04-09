import argparse
import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from meta_uploader import (
    find_existing_facebook_video_by_caption_marker,
    find_existing_instagram_media_by_caption_marker,
    get_last_operation_status,
    upload_fb_reel,
    upload_fb_video_standard,
    upload_fb_file_handle,
)
from run_jornada1_normal import (
    ACTIVE_STATUSES,
    build_caption,
    build_plan,
    clear_active_summary_fields,
    evaluate_ig_video_preflight,
    load_existing_calendar,
    load_queue,
    merge_existing_calendar,
    now_iso,
    require_upload_opt_in,
    write_calendar,
)


BASE_DIR = Path(__file__).resolve().parent
CALENDAR_FILE = BASE_DIR / "meta_calendar.json"
BOGOTA_TZ = ZoneInfo("America/Bogota")
FINAL_LANE_STATUSES = {
    "published",
    "published_with_ig_skip",
    "scheduled",
    "scheduled_with_ig_skip",
}
SCHEDULE_LABEL_TIMES = {
    "facebook_post": (12, 0),
    "instagram_feed": (12, 5),
    "facebook_reel": (18, 0),
    "instagram_reel": (18, 5),
    "instagram_story": (20, 0),
}
FB_REMOTE_GUARD_PAGE_SIZE = 25
FB_REMOTE_GUARD_MAX_PAGES = 2
IG_REMOTE_GUARD_PAGE_SIZE = 25
IG_REMOTE_GUARD_MAX_PAGES = 2


logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(message)s")


def build_slot_payload(publish_date, label):
    hour, minute = SCHEDULE_LABEL_TIMES[label]
    slot_local = datetime.strptime(publish_date, "%Y-%m-%d").replace(
        hour=hour,
        minute=minute,
        second=0,
        microsecond=0,
        tzinfo=BOGOTA_TZ,
    )
    slot_utc = slot_local.astimezone(timezone.utc)
    return {
        "label": label,
        "scheduled_local": slot_local.isoformat(),
        "scheduled_utc": slot_utc.isoformat().replace("+00:00", "Z"),
        "scheduled_unix": int(slot_utc.timestamp()),
    }


def build_existing_remote_result(label, remote_item, slot):
    result_id = str(remote_item.get("id") or "")
    remote_time = remote_item.get("created_time") or remote_item.get("timestamp") or "sin fecha"
    permalink = remote_item.get("permalink_url") or remote_item.get("permalink")
    message = f"ya existia remoto con id {result_id} ({remote_time})"
    if permalink:
        message = f"{message} | {permalink}"
    return {
        "result": result_id,
        "scheduled": slot,
        "status": {
            "kind": "already_exists_remote",
            "phase": "remote_guard",
            "message": message,
            "transient": False,
            "watchdog_alerted": False,
        },
    }


def build_scheduled_remote_result(label, result_id, slot):
    return {
        "result": str(result_id),
        "scheduled": slot,
        "status": {
            "kind": "scheduled_remote",
            "phase": "facebook_schedule",
            "message": f"{result_id} -> {slot['scheduled_local']}",
            "transient": False,
            "watchdog_alerted": False,
        },
    }


def build_scheduled_local_result(label, slot):
    return {
        "result": None,
        "scheduled": slot,
        "status": {
            "kind": "scheduled_local",
            "phase": "local_schedule",
            "message": slot["scheduled_local"],
            "transient": False,
            "watchdog_alerted": False,
        },
    }


def build_skipped_result(kind, message):
    return {
        "result": None,
        "status": {
            "kind": kind,
            "phase": "preflight",
            "message": message,
            "transient": False,
            "watchdog_alerted": False,
        },
    }


def schedule_story_if_enabled(day_entry):
    story = day_entry["instagram_story"]
    if not story.get("enabled") or not story.get("path"):
        return True
    if story.get("status") in FINAL_LANE_STATUSES or story.get("status") == "scheduled_local":
        return True

    slot = build_slot_payload(day_entry["fecha"], "instagram_story")
    story["result"] = None
    story["scheduled"] = slot
    story["status"] = "scheduled_local"
    story["operation_status"] = {
        "kind": "scheduled_local",
        "phase": "local_schedule",
        "message": slot["scheduled_local"],
        "transient": False,
        "watchdog_alerted": False,
    }
    return True


def derive_lane_status(summary):
    kinds = {value.get("status", {}).get("kind") for value in summary.values()}
    if "skipped_requires_second_jornada" in kinds:
        return "scheduled_with_ig_skip"
    return "scheduled"


def schedule_platform_pair(day_entry, lane_name, video_info):
    publish_date = day_entry["fecha"]
    caption = build_caption(video_info, lane_name, publish_date)
    caption_marker = Path(video_info["path"]).stem
    ig_label = "instagram_reel" if lane_name == "reel" else "instagram_feed"
    fb_label = "facebook_reel" if lane_name == "reel" else "facebook_post"
    ig_preflight = evaluate_ig_video_preflight(video_info, lane_name)
    summary = {}

    fb_slot = build_slot_payload(publish_date, fb_label)
    logging.info(
        "Revisando remoto %s para %s antes de programar %s.",
        fb_label,
        video_info["filename"],
        publish_date,
    )
    existing_facebook = find_existing_facebook_video_by_caption_marker(
        caption_marker,
        page_size=FB_REMOTE_GUARD_PAGE_SIZE,
        max_pages=FB_REMOTE_GUARD_MAX_PAGES,
    )
    if existing_facebook:
        logging.warning(
            "Se detecto %s ya existente para %s con id %s. Se conserva y no se reprograma.",
            fb_label,
            video_info["filename"],
            existing_facebook["id"],
        )
        summary[fb_label] = build_existing_remote_result(fb_label, existing_facebook, fb_slot)
    else:
        if lane_name == "reel":
            fb_result = upload_fb_reel(
                video_info["path"],
                caption,
                scheduled_publish_time=fb_slot["scheduled_unix"],
            )
        else:
            fb_result = upload_fb_video_standard(
                video_info["path"],
                caption,
                scheduled_publish_time=fb_slot["scheduled_unix"],
            )
            if not fb_result:
                last_status = get_last_operation_status()
                fallback_allowed = (
                    last_status.get("kind") in {"http_400", "request_exception", "finish_not_confirmed"}
                    and not last_status.get("transient")
                )
                if fallback_allowed:
                    logging.warning(
                        "El finish programado chunked no se confirmo para %s. Se intenta fallback por file handle.",
                        video_info["filename"],
                    )
                    fb_result = upload_fb_file_handle(
                        video_info["path"],
                        caption,
                        scheduled_publish_time=fb_slot["scheduled_unix"],
                    )
        if not fb_result:
            return False, {
                fb_label: {
                    "result": None,
                    "scheduled": fb_slot,
                    "status": get_last_operation_status(),
                }
            }
        summary[fb_label] = build_scheduled_remote_result(fb_label, fb_result, fb_slot)

    if not ig_preflight["compatible"]:
        reason_text = "; ".join(ig_preflight["reasons"])
        logging.warning(
            "Se omite %s para %s en jornada 1: el crudo no cumple specs oficiales de Instagram (%s). "
            "Se deriva a segunda jornada.",
            ig_label,
            video_info["filename"],
            reason_text,
        )
        summary[ig_label] = build_skipped_result("skipped_requires_second_jornada", reason_text)
        return True, summary

    ig_slot = build_slot_payload(publish_date, ig_label)
    logging.info(
        "Revisando remoto %s para %s antes de agendar %s.",
        ig_label,
        video_info["filename"],
        publish_date,
    )
    existing_instagram = find_existing_instagram_media_by_caption_marker(
        caption_marker,
        page_size=IG_REMOTE_GUARD_PAGE_SIZE,
        max_pages=IG_REMOTE_GUARD_MAX_PAGES,
    )
    if existing_instagram:
        logging.warning(
            "Se detecto %s ya existente para %s con id %s. Se conserva y no se reprograma.",
            ig_label,
            video_info["filename"],
            existing_instagram["id"],
        )
        summary[ig_label] = build_existing_remote_result(ig_label, existing_instagram, ig_slot)
    else:
        summary[ig_label] = build_scheduled_local_result(ig_label, ig_slot)

    return True, summary


def schedule_plan(plan):
    for day_entry in plan:
        summary_state = day_entry["summary"].get("status")
        if summary_state == "paused_on_failure":
            logging.error(
                "La agenda sigue pausada por un fallo previo en %s. Revisa %s antes de continuar.",
                day_entry["fecha"],
                CALENDAR_FILE.name,
            )
            return False

        tasks = []
        if day_entry.get("reel"):
            tasks.append(("reel", day_entry["reel"]))
        if day_entry.get("post"):
            tasks.append(("post", day_entry["post"]))
        tasks.sort(key=lambda item: item[1]["size_bytes"], reverse=True)
        day_entry["summary"]["execution_order"] = [lane for lane, _ in tasks]
        day_entry["summary"]["status"] = day_entry["summary"].get("status") or "pending"

        logging.info("======== Agenda Meta | %s ========", day_entry["fecha"])
        logging.info("Orden del dia: %s", ", ".join(day_entry["summary"]["execution_order"]) or "sin assets")

        for lane_name, video_info in tasks:
            lane_entry = day_entry[lane_name]
            if lane_entry.get("status") in FINAL_LANE_STATUSES:
                logging.info(
                    "[%s] %s ya estaba marcado como %s. Se conserva.",
                    lane_name.upper(),
                    video_info["filename"],
                    lane_entry["status"],
                )
                continue

            day_entry["summary"]["status"] = "scheduling"
            day_entry["summary"]["active_lane"] = lane_name
            day_entry["summary"]["active_filename"] = video_info["filename"]
            day_entry["summary"]["last_updated_at"] = now_iso()
            write_calendar(plan)

            ok, lane_summary = schedule_platform_pair(day_entry, lane_name, video_info)
            if not ok:
                lane_entry["status"] = "failed"
                lane_entry["results"] = lane_summary
                lane_entry["last_attempt_finished_at"] = now_iso()
                day_entry["summary"]["status"] = "paused_on_failure"
                day_entry["summary"]["last_updated_at"] = now_iso()
                clear_active_summary_fields(day_entry)
                write_calendar(plan)
                logging.error(
                    "Se pausa la agenda en %s por fallo al programar %s.",
                    day_entry["fecha"],
                    video_info["filename"],
                )
                return False

            lane_entry["status"] = derive_lane_status(lane_summary)
            lane_entry["results"] = lane_summary
            lane_entry["last_attempt_finished_at"] = now_iso()
            day_entry["summary"]["last_updated_at"] = now_iso()
            clear_active_summary_fields(day_entry)
            write_calendar(plan)

        schedule_story_if_enabled(day_entry)
        day_entry["summary"]["status"] = "scheduled"
        day_entry["summary"]["last_updated_at"] = now_iso()
        clear_active_summary_fields(day_entry)
        write_calendar(plan)

    return True


def main():
    parser = argparse.ArgumentParser(
        description="Agenda la jornada 1 en calendario: programa Facebook y deja Instagram en agenda local por dia."
    )
    parser.add_argument("--days", type=int, default=None, help="Cantidad de dias a planificar. Default: toda la cola.")
    parser.add_argument("--start-date", default=None, help="Fecha inicial YYYY-MM-DD. Default: hoy.")
    parser.add_argument("--reel-start-index", type=int, default=0)
    parser.add_argument("--post-start-index", type=int, default=0)
    parser.add_argument("--disable-ig-stories", action="store_true")
    parser.add_argument("--rebuild-plan", action="store_true")
    args = parser.parse_args()

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

    ok = schedule_plan(plan)
    if ok:
        logging.info("Agenda de jornada 1 preparada correctamente.")
        return 0
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
