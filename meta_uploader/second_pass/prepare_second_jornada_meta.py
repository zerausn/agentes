import argparse
import json
from pathlib import Path

from local_clip_optimizer import (
    MANIFEST_DIR,
    PRESETS,
    QUEUE_DIR,
    analyze_video,
    load_json_list,
    sort_paths_by_size_desc,
)


ROOT_DIR = Path(__file__).resolve().parents[1]
DEFAULT_SOURCE_QUEUES = ("posts",)
SUPPORTED_SOURCE_QUEUES = ("posts", "reels")


def load_source_queue(name):
    queue_path = ROOT_DIR / f"pendientes_{name}.json"
    return load_json_list(queue_path)


def choose_source_paths(source_queues, start_index, limit):
    candidates = []
    for source_name in source_queues:
        for path in load_source_queue(source_name):
            candidates.append(str(path))
    ordered = sort_paths_by_size_desc(candidates)
    return ordered[start_index : start_index + limit]


def sync_main_reels_queue(second_pass_queue_name="pendientes_reels_second_pass.json"):
    second_pass_queue = QUEUE_DIR / second_pass_queue_name
    main_queue = ROOT_DIR / "pendientes_reels.json"
    merged = sort_paths_by_size_desc(load_json_list(main_queue) + load_json_list(second_pass_queue))
    with open(main_queue, "w", encoding="utf-8") as handle:
        json.dump(merged, handle, indent=2, ensure_ascii=False)
    return {
        "main_queue": str(main_queue),
        "second_pass_queue": str(second_pass_queue),
        "items": len(merged),
    }


def build_summary(results, sync_summary=None):
    summary = {
        "source_queues": [],
        "processed_sources": [],
        "generated_queues": {},
        "sync_main_reels_queue": sync_summary,
    }
    for item in results:
        summary["source_queues"] = item["source_queues"]
        summary["processed_sources"].append(
            {
                "source": item["source"],
                "manifest_path": item["manifest_path"],
                "rendered_outputs": item["rendered_outputs"],
            }
        )
        for queue_name, queue_path in item["queue_paths"].items():
            summary["generated_queues"][queue_name] = {
                "path": queue_path,
                "items": len(load_json_list(queue_path)),
            }
    return summary


def main():
    parser = argparse.ArgumentParser(
        description="Prepara la segunda jornada de Meta desde material crudo sin tocar originales."
    )
    parser.add_argument(
        "--source-queues",
        nargs="+",
        choices=SUPPORTED_SOURCE_QUEUES,
        default=list(DEFAULT_SOURCE_QUEUES),
        help="Colas crudas a usar como entrada.",
    )
    parser.add_argument("--start-index", type=int, default=0)
    parser.add_argument("--limit", type=int, default=3)
    parser.add_argument("--render-top", type=int, default=1)
    parser.add_argument(
        "--crop-mode",
        choices=["center_crop", "blurpad"],
        default="center_crop",
    )
    parser.add_argument(
        "--presets",
        nargs="+",
        choices=sorted(PRESETS.keys()),
        default=["shared_reel", "instagram_story"],
        help="Presets de segunda jornada a renderizar.",
    )
    parser.add_argument(
        "--skip-normalize",
        action="store_true",
        help="Omitir normalizacion CFR previa.",
    )
    parser.add_argument(
        "--sync-main-reels-queue",
        action="store_true",
        help="Fusiona la cola reel de segunda jornada dentro de pendientes_reels.json.",
    )
    args = parser.parse_args()

    source_paths = choose_source_paths(args.source_queues, args.start_index, args.limit)
    results = []

    for source_path in source_paths:
        manifest_path, manifest = analyze_video(
            source_path,
            crop_mode=args.crop_mode,
            render_top=args.render_top,
            emit_queues=True,
            normalize_first=not args.skip_normalize,
            selected_presets=args.presets,
        )
        queue_paths = {}
        for preset_name in args.presets:
            queue_name = PRESETS[preset_name]["queue_name"]
            if queue_name:
                queue_paths[queue_name] = str(QUEUE_DIR / queue_name)
        results.append(
            {
                "source": str(source_path),
                "source_queues": list(args.source_queues),
                "manifest_path": str(manifest_path),
                "rendered_outputs": manifest["rendered_outputs"],
                "queue_paths": queue_paths,
            }
        )

    sync_summary = None
    if args.sync_main_reels_queue and "shared_reel" in args.presets:
        sync_summary = sync_main_reels_queue()

    summary = build_summary(results, sync_summary=sync_summary)
    summary_path = MANIFEST_DIR / "second_jornada_meta_prepare_summary.json"
    with open(summary_path, "w", encoding="utf-8") as handle:
        json.dump(summary, handle, indent=2, ensure_ascii=False)

    print(f"Resumen guardado en: {summary_path}")
    print(f"Fuentes procesadas: {len(results)}")
    for item in results:
        print(f"- {Path(item['source']).name}")
        for output in item["rendered_outputs"]:
            print(f"  -> {output['preset']}: {output['path']}")
    if sync_summary:
        print(
            "Cola principal de reels actualizada: "
            f"{sync_summary['items']} items en {sync_summary['main_queue']}"
        )


if __name__ == "__main__":
    main()
