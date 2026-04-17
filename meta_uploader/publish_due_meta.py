import argparse
import json
import logging
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from meta_uploader import (
    find_existing_instagram_media_by_caption_marker,
    get_last_operation_status,
    upload_ig_feed_video_resumable,
    upload_ig_reel_resumable,
    upload_ig_story_video_resumable,
)
from run_jornada1_normal import (
    build_caption,
    clear_active_summary_fields,
    load_existing_calendar,
    now_iso,
    require_upload_opt_in,
    write_calendar,
)


BASE_DIR = Path(__file__).resolve().parent
CALENDAR_FILE = BASE_DIR / "meta_calendar.json"
BOGOTA_TZ = ZoneInfo("America/Bogota")


logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(message)s")


def parse_local_slot(slot_blob):
    if not isinstance(slot_blob, dict):
        return None
    slot_value = slot_blob.get("scheduled_local")
    if not slot_value:
        return None
    return datetime.fromisoformat(slot_value)


def publish_due_ig_lane(day_entry, lane_name, lane_entry):
    results = lane_entry.get("results") or {}
    publish_date = day_entry["fecha"]
    video_info = lane_entry
    caption_marker = Path(video_info["path"]).stem

    if lane_name == "post":
        ig_label = "instagram_feed"
        fn = lambda: upload_ig_feed_video_resumable(video_info["path"], build_caption(video_info, lane_name, publish_date))
    else:
        ig_label = "instagram_reel"
        fn = lambda: upload_ig_reel_resumable(video_info["path"], build_caption(video_info, lane_name, publish_date), share_to_feed=False)

    item = results.get(ig_label)
    if not item:
        return True

    status_kind = (item.get("status") or {}).get("kind")
    if status_kind != "scheduled_local":
        return True

    existing_instagram = find_existing_instagram_media_by_caption_marker(caption_marker)
    if existing_instagram:
        item["result"] = existing_instagram["id"]
        item["status"] = {
            "kind": "already_exists_remote",
            "phase": "remote_guard",
            "message": f"ya existia remoto con id {existing_instagram['id']}",
            "transient": False,
            "watchdog_alerted": False,
        }
        return True

    result = fn()
    status = get_last_operation_status()
    if not result:
        item["status"] = status
        return False

    item["result"] = str(result)
    item["status"] = {
        "kind": "success",
        "phase": "instagram_publish_due",
        "message": str(result),
        "transient": False,
        "watchdog_alerted": False,
    }
    return True


def publish_due_story(day_entry):
    story = day_entry.get("instagram_story") or {}
    if story.get("status") != "scheduled_local":
        return True

    result = upload_ig_story_video_resumable(story["path"])
    status = get_last_operation_status()
    if not result:
        story["operation_status"] = status
        return False

    story["result"] = str(result)
    story["status"] = "published"
    story["operation_status"] = {
        "kind": "success",
        "phase": "instagram_story_publish_due",
        "message": str(result),
        "transient": False,
        "watchdog_alerted": False,
    }
    return True


def build_caption(video_info, lane_name, publish_date):
    stem = Path(video_info["path"]).stem
    return f"PW | {publish_date} | {stem}"


def publish_due(plan, now_local):
    for day_entry in plan:
        publish_date = day_entry["fecha"]

        for lane_name in ("post", "reel"):
            lane_entry = day_entry.get(lane_name)
            if not isinstance(lane_entry, dict):
                continue

            results = lane_entry.get("results") or {}
            ig_label = "instagram_feed" if lane_name == "post" else "instagram_reel"
            ig_item = results.get(ig_label)
            slot = parse_local_slot((ig_item or {}).get("scheduled"))
            if slot and now_local >= slot:
                day_entry["summary"]["status"] = "publishing_due"
                day_entry["summary"]["active_lane"] = lane_name
                day_entry["summary"]["active_filename"] = lane_entry["filename"]
                day_entry["summary"]["last_updated_at"] = now_iso()
                write_calendar(plan)
                ok = publish_due_ig_lane(day_entry, lane_name, lane_entry)
                lane_entry["last_attempt_finished_at"] = now_iso()
                day_entry["summary"]["last_updated_at"] = now_iso()
                clear_active_summary_fields(day_entry)
                write_calendar(plan)
                if not ok:
                    day_entry["summary"]["status"] = "paused_on_failure"
                    write_calendar(plan)
                    return False

        story = day_entry.get("instagram_story") or {}
        story_slot = parse_local_slot(story.get("scheduled"))
        if story_slot and now_local >= story_slot:
            day_entry["summary"]["status"] = "publishing_due"
            day_entry["summary"]["active_lane"] = "instagram_story"
            day_entry["summary"]["active_filename"] = Path(story["path"]).name
            day_entry["summary"]["last_updated_at"] = now_iso()
            write_calendar(plan)
            ok = publish_due_story(day_entry)
            day_entry["summary"]["last_updated_at"] = now_iso()
            clear_active_summary_fields(day_entry)
            write_calendar(plan)
            if not ok:
                day_entry["summary"]["status"] = "paused_on_failure"
                write_calendar(plan)
                return False

    return True


def main():
    parser = argparse.ArgumentParser(description="Publica los items locales de Meta cuyo horario ya vencio.")
    parser.add_argument("--now-local", default=None, help="Override ISO local para pruebas.")
    args = parser.parse_args()

    if not require_upload_opt_in():
        return 1

    plan = load_existing_calendar()
    if not plan:
        logging.error("No se encontro %s.", CALENDAR_FILE.name)
        return 1

    now_local = datetime.fromisoformat(args.now_local) if args.now_local else datetime.now(BOGOTA_TZ)
    ok = publish_due(plan, now_local)
    if ok:
        logging.info("Publicacion de items vencidos completada.")
        return 0
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
