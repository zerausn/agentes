import argparse
import json
import logging
import re
import subprocess
import sys
from collections import Counter
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent
ROOT_DIR = BASE_DIR.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from video_helpers import DEFAULT_TITLE_PREFIX
from video_helpers import resolve_ffmpeg_binary
from video_helpers import resolve_ffprobe_binary


LOG_FILE = BASE_DIR / "local_clip_optimizer.log"
NORMALIZED_DIR = BASE_DIR / "normalized"
OUTPUT_DIR = BASE_DIR / "optimized_videos"
MANIFEST_DIR = BASE_DIR / "manifests"
QUEUE_DIR = BASE_DIR / "queues"
SUPPORTED_SUFFIXES = {".mp4", ".mov", ".m4v", ".mkv"}
HOOK_KEYWORDS = (
    "como",
    "como hacer",
    "como funciona",
    "por que",
    "por qué",
    "secreto",
    "error",
    "errores",
    "nunca",
    "jamas",
    "jamás",
    "nadie",
    "mira",
    "ojo",
    "esto",
    "verdad",
    "cambio",
    "aprendi",
    "aprendí",
    "truco",
    "trampa",
    "brutal",
    "increible",
    "increíble",
    "viral",
    "retencion",
    "retención",
)

PRESETS = {
    "youtube_short_hook": {
        "width": 1080,
        "height": 1920,
        "preferred_durations": [20, 30, 45],
        "max_duration": 60,
        "queue_name": "pendientes_second_pass_hook_shorts.json",
        "targets": ["youtube_short"],
    },
    "youtube_short_standard": {
        "width": 1080,
        "height": 1920,
        "preferred_durations": [45, 60, 90, 120, 180],
        "max_duration": 180,
        "queue_name": "pendientes_second_pass_shorts.json",
        "targets": ["youtube_short"],
    },
    "youtube_square_teaser": {
        "width": 1080,
        "height": 1080,
        "preferred_durations": [15, 20, 30, 45, 60],
        "max_duration": 60,
        "queue_name": None,
        "targets": ["youtube_square_teaser"],
    },
}

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[logging.FileHandler(LOG_FILE), logging.StreamHandler()],
)

FFMPEG_BIN = str(resolve_ffmpeg_binary(ROOT_DIR))
FFPROBE_BIN = str(resolve_ffprobe_binary(ROOT_DIR))


def run_command(command):
    return subprocess.run(command, capture_output=True, text=True, check=False)


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
        FFPROBE_BIN,
        "-v",
        "error",
        "-show_entries",
        "format=duration,size:stream=index,codec_type,codec_name,width,height,r_frame_rate,avg_frame_rate,bit_rate",
        "-of",
        "json",
        str(video_path),
    ]
    result = run_command(cmd)
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or f"ffprobe fallo para {video_path}")

    payload = json.loads(result.stdout)
    streams = payload.get("streams") or []
    video_stream = next((stream for stream in streams if stream.get("codec_type") == "video"), {})
    audio_stream = next((stream for stream in streams if stream.get("codec_type") == "audio"), {})
    fmt = payload.get("format") or {}

    return {
        "duration": float(fmt.get("duration") or 0.0),
        "size_bytes": int(fmt.get("size") or 0),
        "video_codec": video_stream.get("codec_name"),
        "audio_codec": audio_stream.get("codec_name"),
        "width": int(video_stream.get("width") or 0),
        "height": int(video_stream.get("height") or 0),
        "fps": str(video_stream.get("r_frame_rate") or ""),
        "avg_fps": str(video_stream.get("avg_frame_rate") or ""),
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
        FFMPEG_BIN,
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
        FFMPEG_BIN,
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
        FFMPEG_BIN,
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
            intervals.append((current_start, float(end_match.group(1))))
            current_start = None
    return intervals


def detect_black_intervals(video_path, min_duration=0.4, pixel_threshold=0.98):
    cmd = [
        FFMPEG_BIN,
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
        match = re.search(r"black_start:(\d+(?:\.\d+)?)\s+black_end:(\d+(?:\.\d+)?)", line)
        if match:
            intervals.append((float(match.group(1)), float(match.group(2))))
    return intervals


def detect_active_crop(video_path, sample_seconds=45):
    cmd = [
        FFMPEG_BIN,
        "-hide_banner",
        "-i",
        str(video_path),
        "-t",
        str(sample_seconds),
        "-vf",
        "cropdetect=24:16:0",
        "-an",
        "-f",
        "null",
        "-",
    ]
    result = run_command(cmd)
    text = (result.stdout or "") + "\n" + (result.stderr or "")
    crops = re.findall(r"crop=(\d+:\d+:\d+:\d+)", text)
    if not crops:
        return None

    most_common = Counter(crops).most_common(1)[0][0]
    width, height, x_pos, y_pos = [int(chunk) for chunk in most_common.split(":")]
    return {"width": width, "height": height, "x": x_pos, "y": y_pos, "filter": most_common}


def parse_timecode(value):
    raw = value.strip().replace(",", ".")
    parts = raw.split(":")
    if len(parts) == 2:
        hours = 0
        minutes = int(parts[0])
        seconds = float(parts[1])
    elif len(parts) == 3:
        hours = int(parts[0])
        minutes = int(parts[1])
        seconds = float(parts[2])
    else:
        raise ValueError(f"Timecode invalido: {value}")
    return hours * 3600 + minutes * 60 + seconds


def parse_srt_or_vtt_text(text):
    cues = []
    blocks = re.split(r"\r?\n\r?\n+", text.strip())
    for block in blocks:
        lines = [line.strip("\ufeff") for line in block.splitlines() if line.strip()]
        if not lines or lines[0].upper() == "WEBVTT":
            continue

        timing_index = 0
        if "-->" not in lines[0]:
            if len(lines) < 2 or "-->" not in lines[1]:
                continue
            timing_index = 1

        timing_line = lines[timing_index]
        text_lines = lines[timing_index + 1 :]
        match = re.match(r"([0-9:.,]+)\s+-->\s+([0-9:.,]+)", timing_line)
        if not match or not text_lines:
            continue

        try:
            start = parse_timecode(match.group(1))
            end = parse_timecode(match.group(2))
        except ValueError:
            continue

        cleaned_text = re.sub(r"<[^>]+>", "", " ".join(text_lines)).strip()
        if cleaned_text:
            cues.append({"start": round(start, 3), "end": round(end, 3), "text": cleaned_text})
    return cues


def parse_json_transcript(payload):
    cues = []
    for segment in payload.get("segments") or []:
        try:
            start = float(segment.get("start"))
            end = float(segment.get("end"))
        except (TypeError, ValueError):
            continue
        text = str(segment.get("text") or "").strip()
        if text:
            cues.append({"start": round(start, 3), "end": round(end, 3), "text": text})
    return cues


def find_transcript_sidecar(video_path):
    source_path = Path(video_path)
    for suffix in (".srt", ".vtt", ".json"):
        candidate = source_path.with_suffix(suffix)
        if candidate.exists():
            return candidate
    return None


def find_subtitle_sidecar(video_path):
    source_path = Path(video_path)
    for suffix in (".srt", ".ass", ".vtt"):
        candidate = source_path.with_suffix(suffix)
        if candidate.exists():
            return candidate
    return None


def load_transcript_cues(video_path):
    sidecar = find_transcript_sidecar(video_path)
    if not sidecar:
        return None, []

    raw_text = sidecar.read_text(encoding="utf-8", errors="ignore")
    if sidecar.suffix.lower() in {".srt", ".vtt"}:
        return sidecar, parse_srt_or_vtt_text(raw_text)
    if sidecar.suffix.lower() == ".json":
        try:
            payload = json.loads(raw_text)
        except json.JSONDecodeError:
            return sidecar, []
        return sidecar, parse_json_transcript(payload)
    return sidecar, []


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


def score_hook_text(text):
    normalized = re.sub(r"\s+", " ", str(text or "")).strip()
    if not normalized:
        return 0.0

    lower = f" {normalized.lower()} "
    keyword_hits = sum(1 for keyword in HOOK_KEYWORDS if keyword in lower)
    word_count = len(re.findall(r"\w+", normalized, flags=re.UNICODE))
    question_bonus = 0.9 if "?" in normalized or normalized.lower().startswith(("como", "cómo", "por que", "por qué", "que", "qué")) else 0.0
    negation_bonus = 0.7 if any(token in lower for token in (" no ", " nunca", " jamas ", " jamás ", " nadie")) else 0.0
    urgency_bonus = 0.5 if "!" in normalized or any(token in lower for token in ("ahora", "hoy", "ojo", "mira")) else 0.0
    number_bonus = 0.4 if re.search(r"\b\d+\b", normalized) else 0.0
    length_bonus = 0.5 if 4 <= word_count <= 18 else 0.0
    score = keyword_hits * 0.45 + question_bonus + negation_bonus + urgency_bonus + number_bonus + length_bonus
    return round(min(4.0, score), 3)


def transcript_stats_for_window(start, end, transcript_cues):
    if not transcript_cues:
        return {
            "hook_text": "",
            "hook_score": 0.0,
            "intro_speech_ratio": 0.0,
            "window_speech_ratio": 0.0,
        }

    duration = max(end - start, 0.01)
    window_cues = [cue for cue in transcript_cues if cue["end"] >= start and cue["start"] <= end]
    if not window_cues:
        return {
            "hook_text": "",
            "hook_score": 0.0,
            "intro_speech_ratio": 0.0,
            "window_speech_ratio": 0.0,
        }

    intro_end = min(end, start + 4.0)
    intro_cues = [cue for cue in window_cues if cue["end"] >= start and cue["start"] <= intro_end]
    hook_candidates = intro_cues or window_cues
    best_hook = max(hook_candidates, key=lambda cue: score_hook_text(cue["text"]))

    window_coverage = 0.0
    intro_coverage = 0.0
    for cue in window_cues:
        overlap = max(0.0, min(end, cue["end"]) - max(start, cue["start"]))
        window_coverage += overlap
        if cue["end"] >= start and cue["start"] <= intro_end:
            intro_overlap = max(0.0, min(intro_end, cue["end"]) - max(start, cue["start"]))
            intro_coverage += intro_overlap

    intro_duration = max(intro_end - start, 0.01)
    return {
        "hook_text": best_hook["text"],
        "hook_score": score_hook_text(best_hook["text"]),
        "intro_speech_ratio": round(min(1.0, intro_coverage / intro_duration), 3),
        "window_speech_ratio": round(min(1.0, window_coverage / duration), 3),
    }


def build_candidate_starts(total_duration, duration, scenes, silences, transcript_cues):
    upper_bound = max(0.0, total_duration - duration)
    starts = {0.0, round(upper_bound, 2)}

    for scene in scenes:
        for offset in (0.0, -0.8, -2.0):
            starts.add(round(max(0.0, min(upper_bound, scene + offset)), 2))

    for _, silence_end in silences:
        starts.add(round(max(0.0, min(upper_bound, silence_end)), 2))

    for cue in transcript_cues:
        starts.add(round(max(0.0, min(upper_bound, cue["start"] - 0.4)), 2))

    return sorted(starts)


def score_window(start, duration, total_duration, scenes, silences, blacks, transcript_cues):
    end = start + duration
    scene_count = count_scenes(start, end, scenes)
    scene_density = scene_count / max(duration / 5.0, 1.0)
    silence_ratio = interval_overlap_ratio(start, end, silences)
    black_ratio = interval_overlap_ratio(start, end, blacks)
    intro_silence_ratio = interval_overlap_ratio(start, min(end, start + 3.0), silences)
    speech_ratio = max(0.0, 1.0 - silence_ratio)
    early_bonus = max(0.0, 1.0 - (start / max(total_duration, 1.0)))
    hook_scene_bonus = 1.0 if has_hook_scene(start, scenes) else 0.0
    transcript_stats = transcript_stats_for_window(start, end, transcript_cues)
    transcript_bonus = (
        transcript_stats["hook_score"] * 0.9
        + transcript_stats["intro_speech_ratio"] * 1.8
        + transcript_stats["window_speech_ratio"] * 0.8
    )

    score = (
        scene_density * 2.4
        + speech_ratio * 3.8
        + early_bonus * 0.8
        + hook_scene_bonus * 1.0
        + transcript_bonus
        - black_ratio * 6.0
        - intro_silence_ratio * 2.5
    )

    reasons = []
    if transcript_stats["hook_text"]:
        reasons.append("abre con hook textual fuerte")
    if hook_scene_bonus:
        reasons.append("entra cerca de un cambio de escena")
    if scene_density >= 1.0:
        reasons.append("mantiene densidad visual alta")
    if speech_ratio >= 0.85:
        reasons.append("sostiene presencia de voz")
    if black_ratio == 0:
        reasons.append("evita transiciones negras")
    if intro_silence_ratio <= 0.1:
        reasons.append("evita silencio al arranque")
    if start < max(15.0, total_duration * 0.15):
        reasons.append("entra temprano al material")

    return {
        "start": round(start, 2),
        "end": round(end, 2),
        "duration": round(duration, 2),
        "score": round(score, 3),
        "scene_count": scene_count,
        "scene_density": round(scene_density, 3),
        "speech_ratio": round(speech_ratio, 3),
        "silence_ratio": round(silence_ratio, 3),
        "intro_silence_ratio": round(intro_silence_ratio, 3),
        "black_ratio": round(black_ratio, 3),
        "hook_text": transcript_stats["hook_text"],
        "hook_score": transcript_stats["hook_score"],
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


def cleanup_packaging_text(text, max_words=10):
    cleaned = re.sub(r"\s+", " ", str(text or "")).strip()
    cleaned = re.sub(r"[\"'`]+", "", cleaned)
    cleaned = cleaned.strip(" .,:;!?-")
    if not cleaned:
        return ""
    words = cleaned.split()
    if len(words) > max_words:
        cleaned = " ".join(words[:max_words]).rstrip(".,:;!?")
    return cleaned


def build_title_suggestion(source_path, preset_name, hook_text):
    cleaned_hook = cleanup_packaging_text(hook_text, max_words=10)
    if cleaned_hook:
        return f"{DEFAULT_TITLE_PREFIX} Clip | {cleaned_hook}"
    return f"{DEFAULT_TITLE_PREFIX} Clip | {source_path.stem} | {preset_name}"


def build_description_suggestion(source_path, candidate):
    hook_text = cleanup_packaging_text(candidate.get("hook_text"), max_words=18)
    if not hook_text:
        hook_text = "Clip optimizado localmente para una segunda jornada de publicacion."

    lines = [
        hook_text,
        "",
        f"Clip derivado de {source_path.name}.",
        (
            "Ventana seleccionada por analisis local de escena, silencio, transiciones y hook "
            f"entre {candidate['start']:.2f}s y {candidate['end']:.2f}s."
        ),
        "",
        "Segunda jornada de clipping orientada a retencion y descubrimiento.",
    ]
    return "\n".join(lines)


def build_tags_suggestion(candidate):
    base_tags = ["shorts", "clipping", "retencion", "video optimizado", "performatic writings"]
    if candidate.get("hook_text"):
        hook_tokens = re.findall(r"\w+", candidate["hook_text"].lower(), flags=re.UNICODE)
        base_tags.extend(token for token in hook_tokens[:4] if len(token) >= 4)

    deduped = []
    seen = set()
    for tag in base_tags:
        normalized = tag.strip().lower()
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        deduped.append(tag)
    return deduped


def top_candidates_for_preset(video_meta, preset, scenes, silences, blacks, transcript_cues, top_k=5):
    candidates = []
    total_duration = video_meta["duration"]

    for duration in choose_durations(total_duration, preset):
        for start in build_candidate_starts(total_duration, duration, scenes, silences, transcript_cues):
            candidates.append(score_window(start, duration, total_duration, scenes, silences, blacks, transcript_cues))

    return dedupe_candidates(candidates)[:top_k]


def build_video_filter(preset, crop_mode, subtitle_path=None, active_crop=None):
    width = preset["width"]
    height = preset["height"]

    prefix = ""
    if active_crop:
        prefix = f"crop={active_crop['width']}:{active_crop['height']}:{active_crop['x']}:{active_crop['y']},"

    if crop_mode == "blurpad":
        background = (
            f"{prefix}split[base][fg];[base]scale={width}:{height}:force_original_aspect_ratio=increase,"
            f"boxblur=20:1,crop={width}:{height}[bg];[fg]scale={width}:{height}:force_original_aspect_ratio=decrease"
            f"[front];[bg][front]overlay=(W-w)/2:(H-h)/2,format=yuv420p"
        )
        filter_graph = background
    else:
        filter_graph = (
            f"{prefix}scale={width}:{height}:force_original_aspect_ratio=increase,"
            f"crop={width}:{height},format=yuv420p"
        )

    if subtitle_path:
        filter_graph += f",subtitles='{ffmpeg_escape_filter_path(subtitle_path)}'"
    return filter_graph


def render_clip(source_path, preset_name, candidate, crop_mode="center_crop", burn_subtitles=True, active_crop=None):
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    preset = PRESETS[preset_name]
    subtitle_path = find_subtitle_sidecar(source_path) if burn_subtitles else None
    output_name = (
        f"{Path(source_path).stem}__{preset_name}__{candidate['start']:.2f}s__"
        f"{int(candidate['duration'])}s.mp4"
    )
    output_path = OUTPUT_DIR / output_name
    video_filter = build_video_filter(preset, crop_mode, subtitle_path=subtitle_path, active_crop=active_crop)

    command = [
        FFMPEG_BIN,
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
    for path in Path(target_path).rglob("*"):
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
        files = sorted(iter_video_files(directory), key=lambda item: item.stat().st_size, reverse=True)[:limit]
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
        logging.info("Normalizando VFR a CFR para %s", source_path.name)
        analysis_path = normalize_to_cfr(source_path)

    video_meta = probe_video(analysis_path)
    scenes = detect_scene_changes(analysis_path)
    silences = detect_silence_intervals(analysis_path)
    blacks = detect_black_intervals(analysis_path)
    active_crop = detect_active_crop(analysis_path)
    transcript_sidecar, transcript_cues = load_transcript_cues(analysis_path)
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
            "active_crop": active_crop,
            "transcript_sidecar": str(transcript_sidecar) if transcript_sidecar else None,
            "transcript_cue_count": len(transcript_cues),
        },
        "presets": {},
        "rendered_outputs": [],
    }

    queue_accumulator = {}

    for preset_name in preset_names:
        preset = PRESETS[preset_name]
        candidates = top_candidates_for_preset(video_meta, preset, scenes, silences, blacks, transcript_cues)
        for candidate in candidates:
            candidate["title_suggestion"] = build_title_suggestion(source_path, preset_name, candidate.get("hook_text"))
            candidate["description_suggestion"] = build_description_suggestion(source_path, candidate)
            candidate["tags_suggestion"] = build_tags_suggestion(candidate)

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
                    active_crop=active_crop,
                )
                rendered = {
                    "preset": preset_name,
                    "targets": preset["targets"],
                    "path": str(output_path),
                    "source": str(source_path),
                    "start": candidate["start"],
                    "end": candidate["end"],
                    "duration": candidate["duration"],
                    "score": candidate["score"],
                    "reason_summary": candidate["reason_summary"],
                    "hook_text": candidate["hook_text"],
                    "title_suggestion": candidate["title_suggestion"],
                    "description_suggestion": candidate["description_suggestion"],
                    "tags_suggestion": candidate["tags_suggestion"],
                }
                manifest["rendered_outputs"].append(rendered)
                if emit_queues and preset["queue_name"]:
                    queue_accumulator.setdefault(preset["queue_name"], []).append(rendered)

    manifest_path = MANIFEST_DIR / f"{source_path.stem}__second_pass_manifest.json"
    with manifest_path.open("w", encoding="utf-8") as handle:
        json.dump(manifest, handle, indent=2, ensure_ascii=False)

    if emit_queues:
        for queue_name, entries in queue_accumulator.items():
            queue_path = QUEUE_DIR / queue_name
            existing = []
            if queue_path.exists():
                try:
                    existing = json.loads(queue_path.read_text(encoding="utf-8"))
                except json.JSONDecodeError:
                    existing = []

            merged = {}
            for entry in existing + entries:
                merged[str(entry["path"])] = entry
            queue_path.write_text(json.dumps(list(merged.values()), indent=2, ensure_ascii=False), encoding="utf-8")

    return manifest_path, manifest


def print_summary(manifest_path, manifest):
    print(f"Manifest guardado en: {manifest_path}")
    print(f"Video fuente: {manifest['source']}")
    meta = manifest["meta"]
    print(
        f"Duracion={meta['duration']:.2f}s | Resolucion={meta['width']}x{meta['height']} | "
        f"Tamanio={round(meta['size_bytes'] / (1024 * 1024), 1)} MB"
    )
    if manifest["analysis"]["transcript_sidecar"]:
        print(f"Transcript usado: {manifest['analysis']['transcript_sidecar']}")
    if manifest["analysis"]["active_crop"]:
        print(f"Crop detectado: {manifest['analysis']['active_crop']['filter']}")

    for preset_name, preset_blob in manifest["presets"].items():
        print(f"\n[{preset_name}] targets={', '.join(preset_blob['targets'])}")
        for candidate in preset_blob["candidates"][:3]:
            hook_preview = candidate["hook_text"][:50] if candidate["hook_text"] else "sin hook textual"
            print(
                f"  start={candidate['start']:>6}s | dur={candidate['duration']:>5}s | "
                f"score={candidate['score']:>5} | hook={hook_preview}"
            )

    if manifest["rendered_outputs"]:
        print("\nOutputs renderizados:")
        for item in manifest["rendered_outputs"]:
            print(f"  - {item['preset']}: {item['path']}")


def main():
    parser = argparse.ArgumentParser(
        description="Segunda jornada para YouTube: analisis local, clipping y render sin tocar el uploader base."
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--input", help="Ruta a un video fuente")
    group.add_argument("--input-dir", help="Ruta a una carpeta de videos")
    parser.add_argument("--limit", type=int, default=1, help="Cuantos videos tomar si se usa --input-dir")
    parser.add_argument("--render-top", type=int, default=0, help="Cuantos clips renderizar por preset")
    parser.add_argument("--crop-mode", choices=["center_crop", "blurpad"], default="center_crop", help="Modo de encuadre local")
    parser.add_argument("--emit-queues", action="store_true", help="Emitir colas locales separadas de la segunda jornada")
    parser.add_argument(
        "--presets",
        nargs="+",
        choices=sorted(PRESETS.keys()),
        default=list(PRESETS.keys()),
        help="Presets a analizar/renderizar",
    )
    parser.add_argument(
        "--skip-normalize",
        action="store_true",
        help="Omitir la normalizacion previa a CFR aunque el archivo parezca VFR",
    )
    args = parser.parse_args()

    for source_path in select_inputs(args.input, args.input_dir, args.limit):
        logging.info("Analizando segunda jornada para %s", source_path.name)
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
