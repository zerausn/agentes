import json
from datetime import datetime
from pathlib import Path

def generate_report():
    calendar_path = Path("meta_uploader/meta_calendar.json")
    if not calendar_path.exists():
        print("No se encontro meta_calendar.json")
        return

    with open(calendar_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    # Buscar entradas con éxito en Facebook
    successes = []
    for entry in data:
        post = entry.get("post")
        if not post: continue
        
        res = post.get("results", {}).get("facebook_post", {})
        if res.get("status", {}).get("kind") == "scheduled_remote" or res.get("status", {}).get("kind") == "success":
            finish_at = post.get("last_attempt_finished_at")
            if finish_at:
                sched_time = res.get("scheduled", {}).get("scheduled_local", "Publicado AHORA")
                successes.append({
                    "filename": post.get("filename"),
                    "finished_at": finish_at,
                    "scheduled_for": sched_time
                })

    # Ordenar por fecha de subida (descendente)
    successes.sort(key=lambda x: x["finished_at"], reverse=True)

    # Tomar las últimas 20
    last_20 = successes[:20]

    print(f"{'ARCHIVO':<30} | {'SUBIDA EXITOSA':<20} | {'PROGRAMADO PARA'}")
    print("-" * 80)
    for s in last_20:
        print(f"{s['filename']:<30} | {s['finished_at']:<20} | {s['scheduled_for']}")

if __name__ == "__main__":
    generate_report()
