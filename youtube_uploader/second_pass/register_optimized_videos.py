import argparse
import json
import logging
import sys
from datetime import datetime
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent
ROOT_DIR = BASE_DIR.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from video_helpers import ensure_basic_video_fields
from video_helpers import load_json_file
from video_helpers import probe_video_metadata
from video_helpers import save_json_file


LOG_FILE = BASE_DIR / "register_optimized_videos.log"
JSON_DB = ROOT_DIR / "scanned_videos.json"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[logging.FileHandler(LOG_FILE), logging.StreamHandler()],
)


def load_queue_entries(queue_path):
    payload = json.loads(Path(queue_path).read_text(encoding="utf-8"))
    if payload and isinstance(payload[0], str):
        return [{"path": item} for item in payload]
    return payload


def load_manifest_entries(manifest_path, top_per_preset=1, include_all_rendered=False):
    manifest = json.loads(Path(manifest_path).read_text(encoding="utf-8"))
    rendered_outputs = manifest.get("rendered_outputs") or []
    if include_all_rendered:
        return rendered_outputs

    grouped = {}
    for item in rendered_outputs:
        grouped.setdefault(item.get("preset", "unknown"), []).append(item)

    selected = []
    for _, items in grouped.items():
        items_sorted = sorted(items, key=lambda item: item.get("score", 0), reverse=True)
        selected.extend(items_sorted[:top_per_preset])
    return selected


def build_second_pass_record(entry):
    file_path = Path(entry["path"]).resolve()
    if not file_path.exists():
        raise FileNotFoundError(f"No existe el optimizado {file_path}")

    record = {
        "path": str(file_path),
        "filename": file_path.name,
        "size_mb": round(file_path.stat().st_size / (1024 * 1024), 2),
        "uploaded": False,
        "processing_stage": "second_pass",
        "second_pass_source": entry.get("source"),
        "second_pass_preset": entry.get("preset"),
        "second_pass_score": entry.get("score"),
        "second_pass_start": entry.get("start"),
        "second_pass_end": entry.get("end"),
        "second_pass_duration": entry.get("duration"),
        "second_pass_reason": entry.get("reason_summary"),
        "second_pass_hook_text": entry.get("hook_text"),
        "second_pass_registered_at": datetime.now().isoformat(),
    }

    if entry.get("title_suggestion"):
        record["title_override"] = entry["title_suggestion"]
    if entry.get("description_suggestion"):
        record["description_override"] = entry["description_suggestion"]
    if entry.get("tags_suggestion"):
        record["tags_override"] = entry["tags_suggestion"]

    ensure_basic_video_fields(record)
    probe_data = probe_video_metadata(file_path)
    if probe_data:
        record.update(
            {
                "type": probe_data["type"],
                "duration": probe_data["duration"],
                "dimensions": probe_data["dimensions"],
            }
        )
    return record


def merge_registered_records(existing_videos, new_records):
    existing_by_path = {video["path"]: video for video in existing_videos}
    added = 0
    updated = 0

    for record in new_records:
        known = existing_by_path.get(record["path"])
        if known:
            was_uploaded = known.get("uploaded", False)
            known.update(record)
            known["uploaded"] = was_uploaded
            updated += 1
            continue

        existing_videos.append(record)
        existing_by_path[record["path"]] = record
        added += 1

    existing_videos.sort(key=lambda item: item.get("size_mb", 0), reverse=True)
    return added, updated


def collect_entries(args):
    entries = []
    if args.queue:
        entries.extend(load_queue_entries(args.queue))

    manifest_paths = []
    if args.manifest:
        manifest_paths.extend(Path(path).resolve() for path in args.manifest)
    if args.manifest_dir:
        manifest_paths.extend(sorted(Path(args.manifest_dir).resolve().glob("*__second_pass_manifest.json")))

    for manifest_path in manifest_paths:
        entries.extend(
            load_manifest_entries(
                manifest_path,
                top_per_preset=args.top_per_preset,
                include_all_rendered=args.all_rendered,
            )
        )

    deduped = {}
    for entry in entries:
        deduped[str(Path(entry["path"]).resolve())] = entry
    return list(deduped.values())


def main():
    parser = argparse.ArgumentParser(
        description="Registrar clips optimizados de la segunda jornada dentro de scanned_videos.json."
    )
    parser.add_argument("--queue", help="Cola JSON emitida por local_clip_optimizer.py")
    parser.add_argument("--manifest", nargs="+", help="Uno o varios manifests especificos")
    parser.add_argument("--manifest-dir", help="Directorio de manifests a leer")
    parser.add_argument("--top-per-preset", type=int, default=1, help="Cuantos renders tomar por preset desde cada manifest")
    parser.add_argument("--all-rendered", action="store_true", help="Registrar todos los renders encontrados en cada manifest")
    parser.add_argument("--dry-run", action="store_true", help="Solo mostrar que se registraria")
    args = parser.parse_args()

    if not any([args.queue, args.manifest, args.manifest_dir]):
        parser.error("Debes indicar --queue, --manifest o --manifest-dir")

    entries = collect_entries(args)
    if not entries:
        logging.warning("No se encontraron entradas renderizadas para registrar.")
        return

    records = []
    for entry in entries:
        try:
            records.append(build_second_pass_record(entry))
        except FileNotFoundError as exc:
            logging.warning(str(exc))

    if not records:
        logging.warning("No hubo clips validos para registrar.")
        return

    logging.info("Clips listos para registrar: %s", len(records))
    if args.dry_run:
        for record in records:
            logging.info("%s | %s", record["path"], record.get("title_override", record["filename"]))
        return

    existing_videos = load_json_file(JSON_DB, [])
    added, updated = merge_registered_records(existing_videos, records)
    save_json_file(JSON_DB, existing_videos)
    logging.info("Registro completado. Agregados=%s | Actualizados=%s | Total indice=%s", added, updated, len(existing_videos))


if __name__ == "__main__":
    main()
