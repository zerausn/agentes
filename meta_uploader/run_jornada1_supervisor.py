import argparse
import json
import logging
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent
CALENDAR_FILE = BASE_DIR / "meta_calendar.json"
RUNNER_FILE = BASE_DIR / "run_jornada1_normal.py"
SUPERVISOR_LOG_FILE = BASE_DIR / "jornada1_supervisor.log"


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


def inspect_calendar():
    plan = load_calendar()
    today_iso = datetime.now().date().isoformat()
    if not plan:
        return {
            "completed_days": 0,
            "pending_days": 0,
            "running_days": 0,
            "paused_days": 0,
            "all_completed": False,
            "first_incomplete": None,
            "blocked_by_future_day": False,
            "today_iso": today_iso,
        }

    completed_days = sum(1 for day in plan if (day.get("summary") or {}).get("status") == "completed")
    running_days = sum(1 for day in plan if (day.get("summary") or {}).get("status") == "running")
    paused_days = sum(1 for day in plan if (day.get("summary") or {}).get("status") == "paused_on_failure")
    pending_days = len(plan) - completed_days

    first_incomplete = next(
        (
            {
                "fecha": day.get("fecha"),
                "status": (day.get("summary") or {}).get("status"),
                "post": ((day.get("post") or {}).get("filename") if day.get("post") else None),
                "reel": ((day.get("reel") or {}).get("filename") if day.get("reel") else None),
            }
            for day in plan
            if (day.get("summary") or {}).get("status") != "completed"
        ),
        None,
    )

    return {
        "completed_days": completed_days,
        "pending_days": pending_days,
        "running_days": running_days,
        "paused_days": paused_days,
        "all_completed": completed_days == len(plan),
        "first_incomplete": first_incomplete,
        "blocked_by_future_day": bool(
            first_incomplete
            and first_incomplete.get("status") == "pending"
            and (first_incomplete.get("fecha") or "") > today_iso
        ),
        "today_iso": today_iso,
    }


def build_runner_command(args):
    command = [sys.executable, str(RUNNER_FILE), "--days", str(args.days)]
    if args.start_date:
        command.extend(["--start-date", args.start_date])
    if args.reel_start_index:
        command.extend(["--reel-start-index", str(args.reel_start_index)])
    if args.post_start_index:
        command.extend(["--post-start-index", str(args.post_start_index)])
    if args.pause_between_assets != 10:
        command.extend(["--pause-between-assets", str(args.pause_between_assets)])
    if args.max_live_days != 1:
        command.extend(["--max-live-days", str(args.max_live_days)])
    if args.disable_ig_stories:
        command.append("--disable-ig-stories")
    if args.rebuild_plan:
        command.append("--rebuild-plan")
    return command


def main():
    parser = argparse.ArgumentParser(
        description="Supervisor del runner normal de jornada 1. Reanuda desde meta_calendar.json si el runner se detiene."
    )
    parser.add_argument("--days", type=int, default=7)
    parser.add_argument("--start-date", default=None)
    parser.add_argument("--reel-start-index", type=int, default=0)
    parser.add_argument("--post-start-index", type=int, default=0)
    parser.add_argument("--pause-between-assets", type=int, default=10)
    parser.add_argument("--max-live-days", type=int, default=1)
    parser.add_argument("--disable-ig-stories", action="store_true")
    parser.add_argument("--rebuild-plan", action="store_true")
    parser.add_argument("--restart-delay-seconds", type=int, default=15)
    parser.add_argument("--max-restarts", type=int, default=10)
    args = parser.parse_args()

    restart_attempt = 0
    while True:
        calendar_state = inspect_calendar()
        if calendar_state["all_completed"]:
            logging.info("El calendario ya figura como completado. No hace falta relanzar nada.")
            return 0
        if calendar_state["paused_days"]:
            logging.error(
                "Se detecto pausa por fallo en el calendario. Se detiene el supervisor para no reintentar a ciegas. Estado: %s",
                calendar_state["first_incomplete"],
            )
            return 2
        if calendar_state["blocked_by_future_day"]:
            logging.info(
                "El siguiente dia pendiente (%s) aun no corresponde frente a hoy %s. Se detiene el supervisor para respetar 1 publicacion por dia real.",
                calendar_state["first_incomplete"],
                calendar_state["today_iso"],
            )
            return 0

        command = build_runner_command(args)
        logging.info(
            "Lanzando runner normal (intento %s/%s). Pendiente actual: %s",
            restart_attempt + 1,
            args.max_restarts + 1,
            calendar_state["first_incomplete"],
        )
        child = subprocess.run(command, cwd=BASE_DIR)
        calendar_state = inspect_calendar()

        if calendar_state["all_completed"]:
            logging.info("La jornada quedo completada despues del intento %s.", restart_attempt + 1)
            return 0
        if calendar_state["paused_days"]:
            logging.error(
                "El runner termino dejando la jornada pausada por fallo. Se corta el supervisor. Estado: %s",
                calendar_state["first_incomplete"],
            )
            return 2
        if calendar_state["blocked_by_future_day"]:
            logging.info(
                "El runner dejo el siguiente dia pendiente (%s) para mas adelante. Hoy es %s, asi que el supervisor se detiene sin relanzar.",
                calendar_state["first_incomplete"],
                calendar_state["today_iso"],
            )
            return 0

        restart_attempt += 1
        if restart_attempt > args.max_restarts:
            logging.error(
                "Se alcanzo el limite de reinicios (%s). El calendario sigue incompleto: %s",
                args.max_restarts,
                calendar_state["first_incomplete"],
            )
            return 1

        logging.warning(
            "El runner termino con codigo %s antes de completar la jornada. Se reintentara en %ss. Pendiente actual: %s",
            child.returncode,
            args.restart_delay_seconds,
            calendar_state["first_incomplete"],
        )
        time.sleep(args.restart_delay_seconds)


if __name__ == "__main__":
    raise SystemExit(main())
