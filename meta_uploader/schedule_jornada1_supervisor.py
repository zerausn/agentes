import argparse
import json
import logging
import os
import subprocess
import sys
import time
from pathlib import Path

from run_jornada1_normal import clear_active_summary_fields, load_queue, now_iso, write_calendar


BASE_DIR = Path(__file__).resolve().parent
CALENDAR_FILE = BASE_DIR / "meta_calendar.json"
RUNNER_FILE = BASE_DIR / "schedule_jornada1_meta.py"
SUPERVISOR_LOG_FILE = BASE_DIR / "schedule_jornada1_supervisor.log"
FINAL_DAY_STATUSES = {"scheduled", "completed"}
FAILED_LANE_STATUSES = {"failed"}


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[logging.FileHandler(SUPERVISOR_LOG_FILE, encoding="utf-8"), logging.StreamHandler()],
)


def load_calendar():
    if not CALENDAR_FILE.exists():
        return []
    try:
        with open(CALENDAR_FILE, "r", encoding="utf-8") as handle:
            payload = json.load(handle)
        return payload if isinstance(payload, list) else []
    except Exception as exc:
        logging.warning("No se pudo leer %s: %s", CALENDAR_FILE.name, exc)
        return []


def iter_day_lanes(day_entry):
    for lane_name in ("reel", "post"):
        lane_entry = day_entry.get(lane_name)
        if lane_entry:
            yield lane_name, lane_entry


def inspect_calendar():
    plan = load_calendar()
    if not plan:
        return {
            "all_completed": False,
            "calendar_days": 0,
            "scheduled_days": 0,
            "pending_days": 0,
            "paused_days": 0,
            "first_incomplete": None,
        }

    scheduled_days = sum(
        1 for day in plan if (day.get("summary") or {}).get("status") in FINAL_DAY_STATUSES
    )
    paused_days = sum(1 for day in plan if (day.get("summary") or {}).get("status") == "paused_on_failure")
    first_incomplete = next(
        (
            {
                "fecha": day.get("fecha"),
                "status": (day.get("summary") or {}).get("status"),
                "post": ((day.get("post") or {}).get("filename") if day.get("post") else None),
                "reel": ((day.get("reel") or {}).get("filename") if day.get("reel") else None),
            }
            for day in plan
            if (day.get("summary") or {}).get("status") not in FINAL_DAY_STATUSES
        ),
        None,
    )
    return {
        "all_completed": scheduled_days == len(plan),
        "calendar_days": len(plan),
        "scheduled_days": scheduled_days,
        "pending_days": len(plan) - scheduled_days,
        "paused_days": paused_days,
        "first_incomplete": first_incomplete,
    }


def desired_calendar_days(args):
    reels = load_queue("reels")
    posts = load_queue("posts")
    max_available = max(len(reels) - args.reel_start_index, len(posts) - args.post_start_index, 0)
    if args.days is None:
        return max_available
    return min(args.days, max_available)


def find_transient_failure(plan):
    for day_entry in plan:
        if (day_entry.get("summary") or {}).get("status") != "paused_on_failure":
            continue
        for lane_name, lane_entry in iter_day_lanes(day_entry):
            if lane_entry.get("status") not in FAILED_LANE_STATUSES:
                continue
            results = lane_entry.get("results") or {}
            for route_name, route_result in results.items():
                status = (route_result or {}).get("status") or {}
                if status.get("transient"):
                    return {
                        "day_entry": day_entry,
                        "lane_name": lane_name,
                        "lane_entry": lane_entry,
                        "route_name": route_name,
                        "status": status,
                    }
            return {
                "day_entry": day_entry,
                "lane_name": lane_name,
                "lane_entry": lane_entry,
                "route_name": None,
                "status": None,
            }
    return None


def reset_transient_failure(plan, *, max_retries_per_lane):
    failure = find_transient_failure(plan)
    if not failure:
        return {"reset": False, "reason": "no_failure"}

    day_entry = failure["day_entry"]
    lane_entry = failure["lane_entry"]
    lane_name = failure["lane_name"]
    status = failure["status"]
    if not status or not status.get("transient"):
        return {
            "reset": False,
            "reason": "non_transient",
            "fecha": day_entry.get("fecha"),
            "lane_name": lane_name,
            "status": status,
        }

    retries = int(lane_entry.get("supervisor_retry_count") or 0)
    if retries >= max_retries_per_lane:
        return {
            "reset": False,
            "reason": "retry_limit_reached",
            "fecha": day_entry.get("fecha"),
            "lane_name": lane_name,
            "retry_count": retries,
            "status": status,
        }

    lane_entry["supervisor_retry_count"] = retries + 1
    lane_entry["supervisor_last_transient_failure"] = {
        "route_name": failure["route_name"],
        "status": status,
        "reset_at": now_iso(),
    }
    lane_entry["status"] = "pending"
    lane_entry.pop("results", None)
    lane_entry.pop("last_attempt_finished_at", None)
    day_entry["summary"]["status"] = "pending"
    day_entry["summary"]["last_updated_at"] = now_iso()
    clear_active_summary_fields(day_entry)
    write_calendar(plan)
    return {
        "reset": True,
        "fecha": day_entry.get("fecha"),
        "lane_name": lane_name,
        "retry_count": lane_entry["supervisor_retry_count"],
        "status": status,
    }


def build_runner_command(args):
    command = [sys.executable, str(RUNNER_FILE)]
    if args.days is not None:
        command.extend(["--days", str(args.days)])
    if args.start_date:
        command.extend(["--start-date", args.start_date])
    if args.reel_start_index:
        command.extend(["--reel-start-index", str(args.reel_start_index)])
    if args.post_start_index:
        command.extend(["--post-start-index", str(args.post_start_index)])
    if args.disable_ig_stories:
        command.append("--disable-ig-stories")
    if args.rebuild_plan:
        command.append("--rebuild-plan")
    return command


def build_child_env(args):
    env = os.environ.copy()
    env.setdefault("META_ENABLE_UPLOAD", "1")
    env["META_UPLOAD_BINARY_RETRY_ATTEMPTS"] = str(args.upload_binary_retry_attempts)
    env["META_HTTP_RETRY_ATTEMPTS"] = str(args.http_retry_attempts)
    env.setdefault("META_FB_UPLOAD_CHUNK_BYTES", str(16 * 1024 * 1024))
    env.setdefault("META_FB_UPLOAD_MIN_CHUNK_BYTES", str(4 * 1024 * 1024))
    env.setdefault("META_PROGRESS_LOG_MIN_INTERVAL_SECONDS", "1.5")
    env.setdefault("META_PROGRESS_LOG_MIN_BYTES", str(8 * 1024 * 1024))
    if args.request_timeout:
        env["META_REQUEST_TIMEOUT"] = str(args.request_timeout)
    return env


def main():
    parser = argparse.ArgumentParser(
        description=(
            "Supervisor de la agenda programada de jornada 1. Reanuda schedule_jornada1_meta.py "
            "y resetea fallos transitorios para que el mismo asset se reintente automaticamente."
        )
    )
    parser.add_argument("--days", type=int, default=None)
    parser.add_argument("--start-date", default=None)
    parser.add_argument("--reel-start-index", type=int, default=0)
    parser.add_argument("--post-start-index", type=int, default=0)
    parser.add_argument("--disable-ig-stories", action="store_true")
    parser.add_argument("--rebuild-plan", action="store_true")
    parser.add_argument("--restart-delay-seconds", type=int, default=20)
    parser.add_argument("--max-restarts", type=int, default=12)
    parser.add_argument("--max-retries-per-lane", type=int, default=6)
    parser.add_argument("--upload-binary-retry-attempts", type=int, default=5)
    parser.add_argument("--http-retry-attempts", type=int, default=5)
    parser.add_argument("--request-timeout", type=int, default=90)
    args = parser.parse_args()

    restart_attempt = 0
    env = build_child_env(args)

    while True:
        state = inspect_calendar()
        target_days = desired_calendar_days(args)
        if state["all_completed"]:
            if target_days and state["calendar_days"] < target_days:
                logging.info(
                    "El calendario actual ya esta completo, pero solo cubre %s de %s dias posibles. "
                    "Se relanza el scheduler para expandir la agenda.",
                    state["calendar_days"],
                    target_days,
                )
            else:
                logging.info("La agenda ya figura como completada. No hace falta relanzar nada.")
                return 0

        plan = load_calendar()
        if state["paused_days"]:
            reset_info = reset_transient_failure(plan, max_retries_per_lane=args.max_retries_per_lane)
            if reset_info.get("reset"):
                logging.warning(
                    "Se detecto un fallo transitorio y se rearmo el lane %s del %s para reintento automatico. "
                    "Intento supervisor %s/%s. Detalle: %s",
                    reset_info["lane_name"],
                    reset_info["fecha"],
                    reset_info["retry_count"],
                    args.max_retries_per_lane,
                    reset_info["status"],
                )
                time.sleep(args.restart_delay_seconds)
            else:
                logging.error(
                    "La agenda quedo pausada y no es seguro relanzarla a ciegas. Estado: %s | reset_info=%s",
                    state["first_incomplete"],
                    reset_info,
                )
                return 2

        command = build_runner_command(args)
        logging.info(
            "Lanzando scheduler programado (intento %s/%s). Pendiente actual: %s",
            restart_attempt + 1,
            args.max_restarts + 1,
            inspect_calendar()["first_incomplete"],
        )
        child = subprocess.run(command, cwd=BASE_DIR, env=env)
        state = inspect_calendar()

        if state["all_completed"]:
            logging.info("La agenda quedo completa despues del intento %s.", restart_attempt + 1)
            return 0

        restart_attempt += 1
        if restart_attempt > args.max_restarts:
            logging.error(
                "Se alcanzo el limite de reinicios (%s). El calendario sigue incompleto: %s",
                args.max_restarts,
                state["first_incomplete"],
            )
            return 1

        logging.warning(
            "El scheduler termino con codigo %s y la agenda sigue incompleta. Se reintentara en %ss. Pendiente actual: %s",
            child.returncode,
            args.restart_delay_seconds,
            state["first_incomplete"],
        )
        time.sleep(args.restart_delay_seconds)


if __name__ == "__main__":
    raise SystemExit(main())
