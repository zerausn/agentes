import json
import os
import re
import subprocess
from datetime import datetime
from pathlib import Path

SUCCESS_DIR_NAME = "videos subidos exitosamente"
EXCLUDED_DIR_NAME = "videos_excluidos_ya_en_youtube"
DEFAULT_TITLE_PREFIX = "PW"
LEGACY_TITLE_MARKER = "Performatic Writings"
TIMESTAMP_STEM_RE = re.compile(r"\b\d{8}_\d{6}\b")


def load_json_file(path, default):
    path = Path(path)
    if not path.exists():
        return default
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def save_json_file(path, payload):
    path = Path(path)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=4, ensure_ascii=False)


def load_config(base_dir):
    return load_json_file(Path(base_dir) / "config.json", {})


def resolve_binary(base_dir, env_name, relative_candidates, fallback_name):
    environ_value = str(os.environ.get(env_name) or "").strip()
    if environ_value:
        candidate = Path(environ_value).expanduser()
        if candidate.exists():
            return candidate

    base_dir = Path(base_dir)
    for relative_path in relative_candidates:
        candidate = (base_dir / relative_path).resolve()
        if candidate.exists():
            return candidate

    return Path(fallback_name)


def resolve_ffmpeg_binary(base_dir):
    return resolve_binary(
        base_dir,
        "YOUTUBE_UPLOADER_FFMPEG",
        [
            "tools/ffmpeg/bin/ffmpeg.exe",
            "tools/ffmpeg/bin/ffmpeg",
        ],
        "ffmpeg",
    )


def resolve_ffprobe_binary(base_dir):
    return resolve_binary(
        base_dir,
        "YOUTUBE_UPLOADER_FFPROBE",
        [
            "tools/ffmpeg/bin/ffprobe.exe",
            "tools/ffmpeg/bin/ffprobe",
        ],
        "ffprobe",
    )


def resolve_config_path(base_dir, raw_path):
    candidate = Path(raw_path).expanduser()
    if not candidate.is_absolute():
        candidate = (Path(base_dir) / candidate).resolve()
    return candidate


def split_env_paths(raw_value):
    return [chunk.strip() for chunk in str(raw_value or "").split(";") if chunk.strip()]


def infer_library_root_from_path(file_path):
    file_path = Path(file_path)
    parent = file_path.parent
    if parent.name.lower() in {SUCCESS_DIR_NAME.lower(), EXCLUDED_DIR_NAME.lower()}:
        return parent.parent
    return parent


def infer_library_roots_from_records(videos):
    roots = []
    seen = set()
    for video in videos or []:
        raw_path = video.get("path")
        if not raw_path:
            continue
        root = infer_library_root_from_path(raw_path)
        root_key = str(root).lower()
        if root_key in seen:
            continue
        seen.add(root_key)
        roots.append(root)
    return roots


def get_video_roots(base_dir, config=None, videos=None, environ=None, existing_only=True):
    config = config or load_config(base_dir)
    environ = environ or os.environ
    scanner_cfg = config.get("scanner", {})

    raw_roots = scanner_cfg.get("video_roots", [])
    if isinstance(raw_roots, str):
        raw_roots = [raw_roots]

    roots = [resolve_config_path(base_dir, raw_path) for raw_path in raw_roots if raw_path]
    roots.extend(resolve_config_path(base_dir, raw_path) for raw_path in split_env_paths(environ.get("YOUTUBE_UPLOADER_VIDEO_ROOTS")))

    if not roots and videos:
        roots = infer_library_roots_from_records(videos)

    unique_roots = []
    seen = set()
    for root in roots:
        key = str(root).lower()
        if key in seen:
            continue
        seen.add(key)
        if existing_only and not root.exists():
            continue
        unique_roots.append(root)
    return unique_roots


def infer_creation_date(file_path):
    file_path = Path(file_path)
    stat = file_path.stat()
    timestamp = getattr(stat, "st_ctime", stat.st_mtime)
    return datetime.fromtimestamp(timestamp).strftime("%Y-%m-%d %H:%M:%S")


def ensure_basic_video_fields(video):
    changed = False
    raw_path = video.get("path")
    if not raw_path:
        return changed

    file_path = Path(raw_path)
    if not video.get("filename"):
        video["filename"] = file_path.name
        changed = True

    if file_path.exists() and not video.get("creation_date"):
        video["creation_date"] = infer_creation_date(file_path)
        changed = True

    return changed


def classify_video_kind(width, height, duration):
    is_vertical_or_square = height >= width
    if is_vertical_or_square:
        return "short" if duration <= 180 else "video"
    return "short" if duration <= 60 else "video"


def parse_ffprobe_stream_data(payload):
    streams = payload.get("streams", [])
    if not streams:
        return None

    stream = streams[0]
    try:
        width = int(stream.get("width") or 0)
        height = int(stream.get("height") or 0)
        duration = float(stream.get("duration") or 0.0)
    except (TypeError, ValueError):
        return None

    if width <= 0 or height <= 0 or duration <= 0:
        return None

    return {
        "width": width,
        "height": height,
        "duration": duration,
        "dimensions": f"{width}x{height}",
        "type": classify_video_kind(width, height, duration),
    }


def probe_video_metadata(file_path, runner=None):
    runner = runner or subprocess.run
    ffprobe_binary = resolve_ffprobe_binary(Path(__file__).resolve().parent)
    command = [
        str(ffprobe_binary),
        "-v",
        "error",
        "-select_streams",
        "v:0",
        "-show_entries",
        "stream=width,height,duration",
        "-of",
        "json",
        str(file_path),
    ]
    try:
        result = runner(command, capture_output=True, text=True, check=False)
    except OSError:
        return None

    if result.returncode != 0 or not result.stdout.strip():
        return None

    try:
        return parse_ffprobe_stream_data(json.loads(result.stdout))
    except json.JSONDecodeError:
        return None


def enrich_video_record(video, include_probe=False):
    changed = ensure_basic_video_fields(video)
    raw_path = video.get("path")
    if not include_probe or not raw_path:
        return changed

    file_path = Path(raw_path)
    if not file_path.exists():
        return changed

    if all(video.get(field) for field in ("type", "duration", "dimensions")):
        return changed

    metadata = probe_video_metadata(file_path)
    if not metadata:
        return changed

    for field in ("type", "duration", "dimensions"):
        if video.get(field) != metadata[field]:
            video[field] = metadata[field]
            changed = True
    return changed


def build_video_title(video, prefix=DEFAULT_TITLE_PREFIX):
    override = str(video.get("title_override") or "").strip()
    if override:
        return override

    filename = video.get("filename")
    raw_path = video.get("path")
    if not filename and raw_path:
        filename = Path(raw_path).name
    filename = filename or "sin_nombre"

    creation_date = video.get("creation_date")
    if not creation_date and raw_path and Path(raw_path).exists():
        creation_date = infer_creation_date(raw_path)
    date_str = str(creation_date or "N/A").split(" ")[0]
    return f"{prefix} | {date_str} | ({Path(filename).stem})"


def coerce_tag_list(raw_tags):
    if isinstance(raw_tags, list):
        return [str(tag).strip() for tag in raw_tags if str(tag).strip()]
    if isinstance(raw_tags, str):
        return [chunk.strip() for chunk in raw_tags.split(",") if chunk.strip()]
    return []


def build_upload_metadata(video, config, prefix=DEFAULT_TITLE_PREFIX):
    default_metadata = config.get("default_metadata", {})

    title = build_video_title(video, prefix=prefix)
    description = str(video.get("description_override") or "").strip() or default_metadata.get("description", "")
    tags = coerce_tag_list(video.get("tags_override")) or coerce_tag_list(default_metadata.get("tags", []))
    category_id = str(video.get("categoryId_override") or default_metadata.get("categoryId", "24"))
    privacy_status = str(video.get("privacyStatus_override") or default_metadata.get("privacyStatus", "private"))
    license_name = str(video.get("license_override") or default_metadata.get("license", "youtube"))

    return {
        "title": title,
        "description": description,
        "tags": tags,
        "categoryId": category_id,
        "privacyStatus": privacy_status,
        "license": license_name,
    }


def is_managed_title(title):
    normalized = (title or "").strip()
    if not normalized:
        return False
    if normalized.startswith(f"{DEFAULT_TITLE_PREFIX} | "):
        return True
    if LEGACY_TITLE_MARKER in normalized:
        return True
    return bool(TIMESTAMP_STEM_RE.search(normalized))
