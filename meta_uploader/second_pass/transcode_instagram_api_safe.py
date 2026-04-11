import argparse
import json
import math
import subprocess
import tempfile
from pathlib import Path

from local_clip_optimizer import (
    MANIFEST_DIR,
    OUTPUT_DIR,
    QUEUE_DIR,
    SUPPORTED_SUFFIXES,
    merge_queue_file,
    probe_video,
)


ROOT_DIR = Path(__file__).resolve().parents[1]
IG_SAFE_QUEUE_NAME = "pendientes_ig_feed_second_pass.json"
IG_SAFE_MAX_BYTES = 290 * 1024 * 1024
IG_SAFE_HARD_LIMIT_BYTES = 300 * 1024 * 1024
IG_SAFE_MAX_WIDTH = 1920
IG_SAFE_MAX_VIDEO_BITRATE_BPS = 25_000_000
IG_SAFE_AUDIO_BITRATE_BPS = 128_000
IG_SAFE_OVERHEAD_BPS = 96_000
IG_SAFE_MIN_VIDEO_BITRATE_BPS = 1_500_000
IG_SAFE_DEFAULT_FPS = 30


def run_command(command):
    return subprocess.run(command, capture_output=True, text=True, check=False)


def parse_frame_rate(value):
    if not value or value == "0/0":
        return 0.0
    if "/" in value:
        left, right = value.split("/", 1)
        try:
            denominator = float(right)
            if denominator == 0:
                return 0.0
            return float(left) / denominator
        except ValueError:
            return 0.0
    try:
        return float(value)
    except ValueError:
        return 0.0


def iter_video_files(target_path):
    for path in target_path.rglob("*"):
        if path.is_file() and path.suffix.lower() in SUPPORTED_SUFFIXES:
            yield path


def select_inputs(input_path=None, input_dir=None, limit=1):
    if input_path:
        path = Path(input_path).resolve()
        if not path.exists():
            raise FileNotFoundError(f"No existe el archivo {path}")
        return [path]

    directory = Path(input_dir).resolve()
    if not directory.exists():
        raise FileNotFoundError(f"No existe el directorio {directory}")

    return sorted(
        iter_video_files(directory),
        key=lambda item: item.stat().st_size,
        reverse=True,
    )[:limit]


def even(value):
    return int(value) // 2 * 2


def compute_scaled_dimensions(width, height, max_width=IG_SAFE_MAX_WIDTH):
    if width <= 0 or height <= 0:
        raise ValueError("No se pudieron leer dimensiones validas del video")

    if width <= max_width:
        return even(width), even(height)

    scale = max_width / width
    return even(max_width), even(height * scale)


def compute_target_video_bitrate(duration_seconds, max_bytes=IG_SAFE_MAX_BYTES):
    total_budget_bps = int((max_bytes * 8) / max(duration_seconds, 1))
    video_budget_bps = total_budget_bps - IG_SAFE_AUDIO_BITRATE_BPS - IG_SAFE_OVERHEAD_BPS
    return max(
        IG_SAFE_MIN_VIDEO_BITRATE_BPS,
        min(IG_SAFE_MAX_VIDEO_BITRATE_BPS, video_budget_bps),
    )


def choose_output_fps(source_fps, preserve_fps=False):
    if preserve_fps and 23.0 <= source_fps <= 60.0:
        return max(23.0, min(60.0, source_fps))
    return float(IG_SAFE_DEFAULT_FPS)


def build_output_path(source_path):
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    return OUTPUT_DIR / f"{Path(source_path).stem}__instagram_api_safe.mp4"


def build_scale_filter(width, height):
    return f"scale={width}:{height}:flags=lanczos,format=yuv420p"


def encode_two_pass(source_path, output_path, width, height, fps_out, video_bitrate_bps):
    MANIFEST_DIR.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=MANIFEST_DIR) as temp_dir:
        passlog = Path(temp_dir) / "ig_api_safe_pass"
        video_bitrate = f"{math.floor(video_bitrate_bps / 1000)}k"
        maxrate = f"{math.floor(min(video_bitrate_bps * 1.15, 24_000_000) / 1000)}k"
        bufsize = f"{math.floor(min(video_bitrate_bps * 2.0, 48_000_000) / 1000)}k"
        scale_filter = build_scale_filter(width, height)
        fps_value = f"{fps_out:.3f}".rstrip("0").rstrip(".")

        pass1 = [
            "ffmpeg",
            "-y",
            "-i",
            str(source_path),
            "-vf",
            scale_filter,
            "-r",
            fps_value,
            "-c:v",
            "libx264",
            "-preset",
            "slow",
            "-profile:v",
            "high",
            "-pix_fmt",
            "yuv420p",
            "-b:v",
            video_bitrate,
            "-maxrate",
            maxrate,
            "-bufsize",
            bufsize,
            "-g",
            "60",
            "-keyint_min",
            "60",
            "-sc_threshold",
            "0",
            "-pass",
            "1",
            "-passlogfile",
            str(passlog),
            "-an",
            "-f",
            "mp4",
            "NUL",
        ]
        result = run_command(pass1)
        if result.returncode != 0:
            raise RuntimeError(result.stderr.strip() or "Fallo el pass 1 de ffmpeg")

        pass2 = [
            "ffmpeg",
            "-y",
            "-i",
            str(source_path),
            "-vf",
            scale_filter,
            "-r",
            fps_value,
            "-c:v",
            "libx264",
            "-preset",
            "slow",
            "-profile:v",
            "high",
            "-pix_fmt",
            "yuv420p",
            "-b:v",
            video_bitrate,
            "-maxrate",
            maxrate,
            "-bufsize",
            bufsize,
            "-g",
            "60",
            "-keyint_min",
            "60",
            "-sc_threshold",
            "0",
            "-movflags",
            "+faststart",
            "-pass",
            "2",
            "-passlogfile",
            str(passlog),
            "-c:a",
            "aac",
            "-ar",
            "48000",
            "-b:a",
            "128k",
            str(output_path),
        ]
        result = run_command(pass2)
        if result.returncode != 0:
            raise RuntimeError(result.stderr.strip() or "Fallo el pass 2 de ffmpeg")


def validate_output(meta):
    reasons = []
    if meta["size_bytes"] > IG_SAFE_HARD_LIMIT_BYTES:
        reasons.append(f"archivo {meta['size_bytes'] / 1e6:.1f} MB > 300 MB")
    if meta["width"] > IG_SAFE_MAX_WIDTH:
        reasons.append(f"ancho {meta['width']}px > {IG_SAFE_MAX_WIDTH}px")
    if meta["video_bitrate"] and meta["video_bitrate"] > IG_SAFE_MAX_VIDEO_BITRATE_BPS:
        reasons.append(
            f"bitrate {meta['video_bitrate'] / 1e6:.2f} Mbps > {IG_SAFE_MAX_VIDEO_BITRATE_BPS / 1e6:.0f} Mbps"
        )
    return {
        "compatible": not reasons,
        "reasons": reasons,
    }


def transcode_instagram_api_safe(source_path, preserve_fps=False, emit_queue=False):
    source_path = Path(source_path).resolve()
    source_meta = probe_video(source_path)
    source_fps = parse_frame_rate(source_meta.get("fps"))
    width_out, height_out = compute_scaled_dimensions(source_meta["width"], source_meta["height"])
    fps_out = choose_output_fps(source_fps, preserve_fps=preserve_fps)
    video_bitrate_bps = compute_target_video_bitrate(source_meta["duration"])
    output_path = build_output_path(source_path)

    encode_two_pass(
        source_path,
        output_path,
        width_out,
        height_out,
        fps_out,
        video_bitrate_bps,
    )

    output_meta = probe_video(output_path)
    validation = validate_output(output_meta)

    manifest = {
        "source": str(source_path),
        "output": str(output_path),
        "source_meta": source_meta,
        "output_meta": output_meta,
        "encoding_plan": {
            "target_width": width_out,
            "target_height": height_out,
            "target_fps": fps_out,
            "target_video_bitrate_bps": video_bitrate_bps,
            "target_audio_bitrate_bps": IG_SAFE_AUDIO_BITRATE_BPS,
            "file_budget_bytes": IG_SAFE_MAX_BYTES,
        },
        "validation": validation,
    }

    MANIFEST_DIR.mkdir(parents=True, exist_ok=True)
    manifest_path = MANIFEST_DIR / f"{source_path.stem}__instagram_api_safe_manifest.json"
    with open(manifest_path, "w", encoding="utf-8") as handle:
        json.dump(manifest, handle, indent=2, ensure_ascii=False)

    queue_path = None
    if emit_queue:
        QUEUE_DIR.mkdir(parents=True, exist_ok=True)
        queue_path = QUEUE_DIR / IG_SAFE_QUEUE_NAME
        merge_queue_file(queue_path, [str(output_path)])

    return manifest_path, manifest, queue_path


def print_summary(manifest_path, manifest, queue_path=None):
    output_meta = manifest["output_meta"]
    validation = manifest["validation"]
    print(f"Manifest guardado en: {manifest_path}")
    print(f"Fuente: {manifest['source']}")
    print(f"Salida: {manifest['output']}")
    print(
        f"Salida final: {output_meta['width']}x{output_meta['height']} | "
        f"{output_meta['duration']:.2f}s | {output_meta['size_bytes'] / 1e6:.1f} MB | "
        f"{output_meta['video_bitrate'] / 1e6:.2f} Mbps"
    )
    if validation["compatible"]:
        print("Validacion IG API-safe: OK")
    else:
        print("Validacion IG API-safe: FALLA")
        for reason in validation["reasons"]:
            print(f"  - {reason}")
    if queue_path:
        print(f"Cola actualizada: {queue_path}")


def main():
    parser = argparse.ArgumentParser(
        description="Segunda jornada: genera una version full-length compatible con la API de Instagram con la maxima calidad posible dentro del limite oficial."
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--input", help="Ruta a un video fuente")
    group.add_argument("--input-dir", help="Ruta a una carpeta de videos")
    parser.add_argument("--limit", type=int, default=1, help="Cuantos videos tomar si se usa --input-dir")
    parser.add_argument(
        "--preserve-fps",
        action="store_true",
        help="Conserva el FPS original si ya cae entre 23 y 60 FPS.",
    )
    parser.add_argument(
        "--emit-queue",
        action="store_true",
        help=f"Agrega las salidas a second_pass/queues/{IG_SAFE_QUEUE_NAME}.",
    )
    args = parser.parse_args()

    for source_path in select_inputs(args.input, args.input_dir, args.limit):
        manifest_path, manifest, queue_path = transcode_instagram_api_safe(
            source_path,
            preserve_fps=args.preserve_fps,
            emit_queue=args.emit_queue,
        )
        print_summary(manifest_path, manifest, queue_path=queue_path)


if __name__ == "__main__":
    main()
