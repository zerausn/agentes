import argparse
import json
import math
import os
import re
import subprocess
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent
NORMALIZED_DIR = BASE_DIR / "normalized"
OUTPUT_DIR = BASE_DIR / "optimized_videos"
MANIFEST_DIR = BASE_DIR / "manifests"
QUEUE_DIR = BASE_DIR / "queues"
SUPPORTED_SUFFIXES = {".mp4", ".mov", ".m4v"}

PRESETS = {
    "shared_reel": {
        "width": 1080,
        "height": 1920,
        "preferred_durations": [20, 30, 45, 60],
        "max_duration": 90,
        "queue_name": "pendientes_reels_second_pass.json",
        "targets": ["facebook_reel", "instagram_reel"],
    },
    "instagram_story": {
        "width": 1080,
        "height": 1920,
        "preferred_durations": [15, 30, 45, 60],
        "max_duration": 60,
        "queue_name": "pendientes_ig_stories_second_pass.json",
        "targets": ["instagram_story"],
    },
    "feed_teaser_square": {
        "width": 1080,
        "height": 1080,
        "preferred_durations": [15, 20, 30, 45],
        "max_duration": 60,
        "queue_name": None,
        "targets": ["future_feed_teaser"],
    },
}


def run_command(command):
    return subprocess.run(command, capture_output=True, text=True, check=False)


def load_json_list(path):
    queue_path = Path(path)
    if not queue_path.exists():
        return []
    try:
        with open(queue_path, "r", encoding="utf-8") as handle:
            payload = json.load(handle)
        if isinstance(payload, list):
            return [str(item) for item in payload]
    except Exception:
        return []
    return []


def sort_paths_by_size_desc(paths):
    unique_paths = []
    seen = set()
    for path in paths:
        normalized = str(path)
        if normalized not in seen:
            seen.add(normalized)
            unique_paths.append(normalized)
    return sorted(
        unique_paths,
        key=lambda item: Path(item).stat().st_size if Path(item).exists() else 0,
        reverse=True,
    )


def merge_queue_file(queue_path, new_paths):
    existing = load_json_list(queue_path)
    merged = sort_paths_by_size_desc(existing + [str(path) for path in new_paths])
    with open(queue_path, "w", encoding="utf-8") as handle:
        json.dump(merged, handle, indent=2, ensure_ascii=False)
    return merged


def ffmpeg_escape_filter_path(path):
    value = str(path).replace("\\", "/")
    value = value.replace(":", r"\:")
    value = value.replace("'", r"\'")
    value = value.replace(",", r"\,")
    value = value.replace("[", r"\[")
    value = value.replace("]", r"\]")
    return value


def probe_video(video_path):
    cmd = [
        "ffprobe",
        "-v",
        "error",
        "-show_entries",
        "format=duration,size:stream=index,codec_type,codec_name,width,height,r_frame_rate,bit_rate",
        "-of",
        "json",
        str(video_path),
    ]
    result = run_command(cmd)
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or f"ffprobe fallo para {video_path}")

    payload = json.loads(result.stdout)
    streams = payload.get("streams") or []
    video_stream = next((s for s in streams if s.get("codec_type") == "video"), {})
    audio_stream = next((s for s in streams if s.get("codec_type") == "audio"), {})
    fmt = payload.get("format") or {}

    return {
        "duration": float(fmt.get("duration") or 0.0),
        "size_bytes": int(fmt.get("size") or 0),
        "video_codec": video_stream.get("codec_name"),
        "audio_codec": audio_stream.get("codec_name"),
        "width": int(video_stream.get("width") or 0),
        "height": int(video_stream.get("height") or 0),
        "fps": video_stream.get("r_frame_rate"),
        "avg_fps": video_stream.get("avg_frame_rate"),
        "video_bitrate": int(video_stream.get("bit_rate") or 0),
        "audio_bitrate": int(audio_stream.get("bit_rate") or 0),
    }


def looks_vfr(video_meta):
    fps = str(video_meta.get("fps") or "")
    avg_fps = str(video_meta.get("avg_fps") or "")
    return bool(fps and avg_fps and fps != avg_fps)


def normalize_to_cfr(source_path, target_fps=30):
    NORMALIZED_DIR.mkdir(parents=True, exist_ok=True)
    output_path = NORMALIZED_DIR / f"{Path(source_path).stem}__cfr.mp4"
    if output_path.exists() and output_path.stat().st_size > 0:
        return output_path

    command = [
        "ffmpeg",
        "-y",
        "-i",
        str(source_path),
        "-vf",
        f"fps={target_fps}",
        "-c:v",
        "libx264",
        "-preset",
        "fast",
        "-crf",
        "20",
        "-c:a",
        "aac",
        "-b:a",
        "192k",
        "-movflags",
        "+faststart",
        str(output_path),
    ]
    result = run_command(command)
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or f"No se pudo normalizar {source_path}")
    return output_path


def detect_scene_changes(video_path, threshold=0.38):
    cmd = [
        "ffmpeg",
        "-hide_banner",
        "-i",
        str(video_path),
        "-vf",
        f"select='gt(scene,{threshold})',showinfo",
        "-an",
        "-f",
        "null",
        "-",
    ]
    result = run_command(cmd)
    text = (result.stdout or "") + "\n" + (result.stderr or "")
    points = []
    for match in re.finditer(r"pts_time:(\d+(?:\.\d+)?)", text):
        points.append(round(float(match.group(1)), 3))
    return sorted(set(points))


def detect_silence_intervals(video_path, noise="-32dB", min_duration=0.4):
    cmd = [
        "ffmpeg",
        "-hide_banner",
        "-i",
        str(video_path),
        "-af",
        f"silencedetect=noise={noise}:d={min_duration}",
        "-f",
        "null",
        "-",
    ]
    result = run_command(cmd)
    text = (result.stdout or "") + "\n" + (result.stderr or "")
    intervals = []
    current_start = None
    for line in text.splitlines():
        start_match = re.search(r"silence_start: (\d+(?:\.\d+)?)", line)
        end_match = re.search(r"silence_end: (\d+(?:\.\d+)?)", line)
        if start_match:
            current_start = float(start_match.group(1))
        elif end_match and current_start is not None:
            end = float(end_match.group(1))
            intervals.append((current_start, end))
            current_start = None
    return intervals


def detect_black_intervals(video_path, min_duration=0.4, pixel_threshold=0.98):
    cmd = [
        "ffmpeg",
        "-hide_banner",
        "-i",
        str(video_path),
        "-vf",
        f"blackdetect=d={min_duration}:pix_th={pixel_threshold}",
        "-an",
        "-f",
        "null",
        "-",
    ]
    result = run_command(cmd)
    text = (result.stdout or "") + "\n" + (result.stderr or "")
    intervals = []
    for line in text.splitlines():
        match = re.search(
            r"black_start:(\d+(?:\.\d+)?)\s+black_end:(\d+(?:\.\d+)?)",
            line,
        )
        if match:
            intervals.append((float(match.group(1)), float(match.group(2))))
    return intervals


def choose_durations(total_duration, preset):
    durations = []
    for value in preset["preferred_durations"]:
        if value <= preset["max_duration"] and value <= total_duration:
            durations.append(float(value))
    if not durations and total_duration > 3:
        durations.append(float(min(total_duration, preset["max_duration"])))
    return durations


def interval_overlap_ratio(start, end, intervals):
    if end <= start:
        return 0.0
    covered = 0.0
    for left, right in intervals:
        overlap = max(0.0, min(end, right) - max(start, left))
        covered += overlap
    return min(1.0, covered / (end - start))


def count_scenes(start, end, scenes):
    return sum(1 for point in scenes if start <= point <= end)


def has_hook_scene(start, scenes, hook_window=2.5):
    return any(start <= point <= start + hook_window for point in scenes)


def build_candidate_starts(total_duration, duration, scenes, silences):
    upper_bound = max(0.0, total_duration - duration)
    starts = {0.0, round(upper_bound, 2)}

    for scene in scenes:
        for offset in (0.0, -1.0, -2.5):
            value = max(0.0, min(upper_bound, scene + offset))
            starts.add(round(value, 2))

    for _, silence_end in silences:
        value = max(0.0, min(upper_bound, silence_end))
        starts.add(round(value, 2))

    return sorted(starts)


def score_window(start, duration, total_duration, scenes, silences, blacks):
    end = start + duration
    scene_count = count_scenes(start, end, scenes)
    scene_density = scene_count / max(duration / 5.0, 1.0)
    silence_ratio = interval_overlap_ratio(start, end, silences)
    black_ratio = interval_overlap_ratio(start, end, blacks)
    speech_ratio = max(0.0, 1.0 - silence_ratio)
    early_bonus = max(0.0, 1.0 - (start / max(total_duration, 1.0)))
    hook_bonus = 1.0 if has_hook_scene(start, scenes) else 0.0

    score = (
        scene_density * 2.8
        + speech_ratio * 4.0
        + early_bonus * 0.8
        + hook_bonus * 1.2
        - black_ratio * 6.0
    )

    reasons = []
    if hook_bonus:
        reasons.append("abre cerca de un cambio de escena")
    if scene_density >= 1.0:
        reasons.append("mantiene densidad visual alta")
    if speech_ratio >= 0.85:
        reasons.append("casi no tiene silencios")
    if black_ratio == 0:
        reasons.append("evita transiciones negras")
    if start < max(15.0, total_duration * 0.15):
        reasons.append("entra temprano al contenido")

    return {
        "start": round(start, 2),
        "end": round(end, 2),
        "duration": round(duration, 2),
        "score": round(score, 3),
        "scene_count": scene_count,
        "scene_density": round(scene_density, 3),
        "speech_ratio": round(speech_ratio, 3),
        "silence_ratio": round(silence_ratio, 3),
        "black_ratio": round(black_ratio, 3),
        "reason_summary": "; ".join(reasons) or "ventana viable sin picos negativos fuertes",
    }


def dedupe_candidates(candidates, tolerance=2.0):
    deduped = []
    for candidate in sorted(candidates, key=lambda item: item["score"], reverse=True):
        keep = True
        for existing in deduped:
            same_duration = abs(existing["duration"] - candidate["duration"]) < 0.2
            same_start = abs(existing["start"] - candidate["start"]) <= tolerance
            if same_duration and same_start:
                keep = False
                break
        if keep:
            deduped.append(candidate)
    return deduped


def top_candidates_for_preset(video_meta, preset, scenes, silences, blacks, top_k=5):
    candidates = []
    total_duration = video_meta["duration"]

    for duration in choose_durations(total_duration, preset):
        for start in build_candidate_starts(total_duration, duration, scenes, silences):
            candidates.append(score_window(start, duration, total_duration, scenes, silences, blacks))

    deduped = dedupe_candidates(candidates)
    return deduped[:top_k]


def find_sidecar_subtitle(video_path):
    source_path = Path(video_path)
    for suffix in (".srt", ".ass", ".vtt"):
        candidate = source_path.with_suffix(suffix)
        if candidate.exists():
            return candidate
    return None


def build_video_filter(preset, crop_mode, subtitle_path=None):
    width = preset["width"]
    height = preset["height"]

    if crop_mode == "blurpad":
        background = (
            f"scale={width}:{height}:force_original_aspect_ratio=increase,"
            f"boxblur=20:1,crop={width}:{height}"
        )
        foreground = f"scale={width}:{height}:force_original_aspect_ratio=decrease"
        filter_graph = (
            f"split[base][fg];[base]{background}[bg];[fg]{foreground}[front];"
            f"[bg][front]overlay=(W-w)/2:(H-h)/2,format=yuv420p"
        )
    else:
        filter_graph = (
            f"scale={width}:{height}:force_original_aspect_ratio=increase,"
            f"crop={width}:{height},format=yuv420p"
        )

    if subtitle_path:
        filter_graph += f",subtitles='{ffmpeg_escape_filter_path(subtitle_path)}'"

    return filter_graph


def render_clip(source_path, preset_name, candidate, crop_mode="center_crop", burn_subtitles=True):
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    preset = PRESETS[preset_name]
    subtitle_path = find_sidecar_subtitle(source_path) if burn_subtitles else None
    output_name = (
        f"{Path(source_path).stem}__{preset_name}__{candidate['start']:.2f}s__"
        f"{int(candidate['duration'])}s.mp4"
    )
    output_path = OUTPUT_DIR / output_name
    video_filter = build_video_filter(preset, crop_mode, subtitle_path=subtitle_path)

    command = [
        "ffmpeg",
        "-y",
        "-ss",
        f"{candidate['start']:.2f}",
        "-i",
        str(source_path),
        "-t",
        f"{candidate['duration']:.2f}",
        "-vf",
        video_filter,
        "-af",
        "loudnorm=I=-16:LRA=11:TP=-1.5",
        "-r",
        "30",
        "-c:v",
        "libx264",
        "-preset",
        "veryfast",
        "-crf",
        "22",
        "-movflags",
        "+faststart",
        "-c:a",
        "aac",
        "-b:a",
        "128k",
        str(output_path),
    ]

    result = run_command(command)
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or f"ffmpeg fallo renderizando {output_name}")

    return output_path


def iter_video_files(target_path):
    for path in target_path.rglob("*"):
        if path.is_file() and path.suffix.lower() in SUPPORTED_SUFFIXES:
            yield path


def select_inputs(input_path=None, input_dir=None, limit=1):
    files = []
    if input_path:
        path = Path(input_path).resolve()
        if not path.exists():
            raise FileNotFoundError(f"No existe el archivo {path}")
        files.append(path)
    else:
        directory = Path(input_dir).resolve()
        if not directory.exists():
            raise FileNotFoundError(f"No existe el directorio {directory}")
        files = sorted(
            iter_video_files(directory),
            key=lambda item: item.stat().st_size,
            reverse=True,
        )[:limit]

    return files


def analyze_video(
    source_path,
    crop_mode="center_crop",
    render_top=0,
    emit_queues=False,
    normalize_first=True,
    selected_presets=None,
):
    MANIFEST_DIR.mkdir(parents=True, exist_ok=True)
    if emit_queues:
        QUEUE_DIR.mkdir(parents=True, exist_ok=True)

    source_path = Path(source_path).resolve()
    source_meta = probe_video(source_path)
    analysis_path = source_path
    if normalize_first and looks_vfr(source_meta):
        analysis_path = normalize_to_cfr(source_path)

    video_meta = probe_video(analysis_path)
    scenes = detect_scene_changes(analysis_path)
    silences = detect_silence_intervals(analysis_path)
    blacks = detect_black_intervals(analysis_path)
    preset_names = selected_presets or list(PRESETS.keys())

    manifest = {
        "source": str(source_path),
        "analysis_source": str(analysis_path),
        "source_meta": source_meta,
        "meta": video_meta,
        "analysis": {
            "scene_changes": scenes,
            "silence_intervals": silences,
            "black_intervals": blacks,
        },
        "presets": {},
        "rendered_outputs": [],
    }

    queue_accumulator = {}

    for preset_name in preset_names:
        preset = PRESETS[preset_name]
        candidates = top_candidates_for_preset(video_meta, preset, scenes, silences, blacks)
        manifest["presets"][preset_name] = {
            "targets": preset["targets"],
            "queue_name": preset["queue_name"],
            "candidates": candidates,
        }

        if render_top > 0:
            for candidate in candidates[:render_top]:
                output_path = render_clip(
                    analysis_path,
                    preset_name,
                    candidate,
                    crop_mode=crop_mode,
                    burn_subtitles=True,
                )
                manifest["rendered_outputs"].append(
                    {
                        "preset": preset_name,
                        "targets": preset["targets"],
                        "path": str(output_path),
                        "start": candidate["start"],
                        "duration": candidate["duration"],
                        "score": candidate["score"],
                    }
                )
                if emit_queues and preset["queue_name"]:
                    queue_accumulator.setdefault(preset["queue_name"], []).append(str(output_path))

    manifest_path = MANIFEST_DIR / f"{source_path.stem}__second_pass_manifest.json"
    with open(manifest_path, "w", encoding="utf-8") as handle:
        json.dump(manifest, handle, indent=2, ensure_ascii=False)

    if emit_queues:
        for queue_name, paths in queue_accumulator.items():
            queue_path = QUEUE_DIR / queue_name
            merge_queue_file(queue_path, paths)

    return manifest_path, manifest


def print_summary(manifest_path, manifest):
    print(f"Manifest guardado en: {manifest_path}")
    print(f"Video fuente: {manifest['source']}")
    meta = manifest["meta"]
    print(
        f"Duracion={meta['duration']:.2f}s | Resolucion={meta['width']}x{meta['height']} | "
        f"Tamanio={round(meta['size_bytes'] / (1024 * 1024), 1)} MB"
    )
    for preset_name, preset_blob in manifest["presets"].items():
        print(f"\n[{preset_name}] targets={', '.join(preset_blob['targets'])}")
        for candidate in preset_blob["candidates"][:3]:
            print(
                f"  start={candidate['start']:>6}s | dur={candidate['duration']:>5}s | "
                f"score={candidate['score']:>5} | {candidate['reason_summary']}"
            )

    if manifest["rendered_outputs"]:
        print("\nOutputs renderizados:")
        for item in manifest["rendered_outputs"]:
            print(f"  - {item['preset']}: {item['path']}")


def main():
    parser = argparse.ArgumentParser(
        description="Segunda jornada: analisis local, clipping y render para Meta sin tocar el uploader base."
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--input", help="Ruta a un video fuente")
    group.add_argument("--input-dir", help="Ruta a una carpeta de videos")
    parser.add_argument("--limit", type=int, default=1, help="Cuantos videos tomar si se usa --input-dir")
    parser.add_argument("--render-top", type=int, default=0, help="Cuantos clips renderizar por preset")
    parser.add_argument(
        "--crop-mode",
        choices=["center_crop", "blurpad"],
        default="center_crop",
        help="Modo de encuadre local para la segunda jornada",
    )
    parser.add_argument(
        "--emit-queues",
        action="store_true",
        help="Emitir colas locales separadas de la segunda jornada",
    )
    parser.add_argument(
        "--presets",
        nargs="+",
        choices=sorted(PRESETS.keys()),
        default=list(PRESETS.keys()),
        help="Presets a analizar/renderizar en esta corrida",
    )
    parser.add_argument(
        "--skip-normalize",
        action="store_true",
        help="Omitir la normalizacion previa a CFR aunque el archivo parezca VFR",
    )
    args = parser.parse_args()

    for source_path in select_inputs(args.input, args.input_dir, args.limit):
        manifest_path, manifest = analyze_video(
            source_path,
            crop_mode=args.crop_mode,
            render_top=args.render_top,
            emit_queues=args.emit_queues,
            normalize_first=not args.skip_normalize,
            selected_presets=args.presets,
        )
        print_summary(manifest_path, manifest)


if __name__ == "__main__":
    main()
