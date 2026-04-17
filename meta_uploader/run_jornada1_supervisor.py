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
    spam_paused_days = sum(1 for day in plan if (day.get("summary") or {}).get("status") == "paused_on_spam")
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
        "spam_paused_days": spam_paused_days,
        "all_completed": completed_days == len(plan),
        "first_incomplete": first_incomplete,
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
    initial_run = True
    while True:
        calendar_state = inspect_calendar()
        
        # Si el calendario esta vacio, necesitamos lanzarlo por primera vez para poblarlo
        if calendar_state["all_completed"]:
            if initial_run:
                logging.info("Arrancando por primera vez (calendario vacio).")
            else:
                logging.info("Todo completado por ahora. Esperando 10s para ver si hay nuevos videos...")
                time.sleep(10)
            
            # Forzamos lanzamiento del runner para poblar
            args.rebuild_plan = True 
        
        elif calendar_state["spam_paused_days"]:
            logging.critical("CRITICO: Estado 'paused_on_spam' detectado. Entrando en enfriamiento preventivo de 24 horas (86400s)...")
            time.sleep(86400)
            
            try:
                plan = load_calendar()
                for day in plan:
                    if (day.get("summary") or {}).get("status") == "paused_on_spam":
                        day["summary"]["status"] = "pending"
                with open(CALENDAR_FILE, "w", encoding="utf-8") as handle:
                    json.dump(plan, handle, indent=2, ensure_ascii=False)
                logging.info("Enfriamiento de 24h finalizado. Estado restaurado para reanudar.")
            except Exception as e:
                logging.error("No se pudo limpiar el calendario tras el enfriamiento: %s", e)
            continue
            
        # Si el calendario tiene errores pero queremos reconstruir o es el inicio, ignoramos el bloqueo
        elif calendar_state["paused_days"] and not (args.rebuild_plan or initial_run):
            logging.error("Pausa por fallo en %s. Reintentando en 60s...", calendar_state["first_incomplete"])
            time.sleep(60)
            continue
            
        initial_run = False

        command = build_runner_command(args)
        logging.info(
            "Lanzando runner normal (cola actual de pendientes: %s)",
            calendar_state["first_incomplete"],
        )
        child = subprocess.run(command, cwd=BASE_DIR)
        calendar_state = inspect_calendar()

        if calendar_state["all_completed"]:
            logging.info("Ciclo terminado exitosamente. Reiniciando en 10s...")
            time.sleep(10)
            restart_attempt = 0
            continue

        if calendar_state["paused_days"]:
            logging.error("Runner termino en fallo. Reintentando en 60s...")
            time.sleep(60)
            restart_attempt += 1  # Solo penalizamos si falla
            continue

        if child.returncode == 0:
            # Runner hizo progreso en background y salio limpio, reiniciar los intentos extra
            restart_attempt = 0
            time.sleep(1)
            continue

        restart_attempt += 1
        if restart_attempt > args.max_restarts:
            logging.error(
                "Se alcanzo el limite maximo de fallos consecutivos (%s). Saliendo.",
                args.max_restarts,
            )
            return 1

        if child.returncode == 36:
            logging.critical("CRITICO: Runner salio con codigo 36 (Spam Code 368). Pausa de seguridad de 24h activada.")
            time.sleep(86400)
            continue

        logging.warning(
            "El runner termino con codigo %s antes de completar la jornada. Se reintentara en %ss. Pendiente: %s",
            child.returncode,
            args.restart_delay_seconds,
            calendar_state["first_incomplete"],
        )
        time.sleep(args.restart_delay_seconds)


if __name__ == "__main__":
    raise SystemExit(main())
