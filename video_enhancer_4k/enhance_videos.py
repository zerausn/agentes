from __future__ import annotations

import argparse
import json
import math
import shutil
import subprocess
import sys
import urllib.request
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent
BIN_DIR = ROOT / "bin"
SAMPLES_DIR = ROOT / "samples"
DEFAULT_SOURCE_DIR = Path(r"/media/zerausn/D69493CF9493B08B/Users/ZN-/Documents\ADM\Nueva carpeta")

GITHUB_API = "https://api.github.com/repos/{repo}/releases/latest"
GITHUB_RELEASES_API = "https://api.github.com/repos/{repo}/releases"

REAL_ESRGAN_REPO = "xinntao/Real-ESRGAN"
RIFE_REPO = "nihui/rife-ncnn-vulkan"


@dataclass(slots=True)
class VideoInfo:
    path: Path
    width: int
    height: int
    fps: float
    duration: float
    codec_name: str
    pix_fmt: str | None
    has_audio: bool


def run(command: list[str], cwd: Path | None = None) -> None:
    print("$", " ".join(f'"{part}"' if " " in part else part for part in command))
    subprocess.run(command, cwd=str(cwd) if cwd else None, check=True)


def run_capture(command: list[str]) -> str:
    result = subprocess.run(command, check=True, capture_output=True, text=True)
    return result.stdout


def parse_fraction(value: str | None) -> float:
    if not value:
        return 0.0
    if "/" in value:
        numerator, denominator = value.split("/", 1)
        return float(numerator) / float(denominator)
    return float(value)


def round_even(value: float) -> int:
    candidate = max(2, int(round(value)))
    return candidate if candidate % 2 == 0 else candidate + 1


def compute_target_dimensions(width: int, height: int, target_vertical: int = 2160) -> tuple[int, int]:
    if width <= 0 or height <= 0:
        raise ValueError("width and height must be positive")

    if height >= width:
        scale = target_vertical / width
    else:
        scale = target_vertical / height

    return round_even(width * scale), round_even(height * scale)


def ensure_parent(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def ffprobe_json(path: Path) -> dict[str, Any]:
    command = [
        "ffprobe",
        "-v",
        "error",
        "-print_format",
        "json",
        "-show_streams",
        "-show_format",
        str(path),
    ]
    return json.loads(run_capture(command))


def probe_video(path: Path) -> VideoInfo:
    data = ffprobe_json(path)
    streams = data.get("streams", [])
    video_stream = next(stream for stream in streams if stream.get("codec_type") == "video")
    audio_stream = next((stream for stream in streams if stream.get("codec_type") == "audio"), None)
    fps = parse_fraction(video_stream.get("avg_frame_rate")) or parse_fraction(video_stream.get("r_frame_rate"))
    duration = float(video_stream.get("duration") or data.get("format", {}).get("duration") or 0.0)
    return VideoInfo(
        path=path,
        width=int(video_stream["width"]),
        height=int(video_stream["height"]),
        fps=fps,
        duration=duration,
        codec_name=video_stream.get("codec_name", "unknown"),
        pix_fmt=video_stream.get("pix_fmt"),
        has_audio=audio_stream is not None,
    )


def inventory_videos(source_dir: Path) -> list[VideoInfo]:
    videos: list[VideoInfo] = []
    for path in sorted(source_dir.glob("*.mp4")):
        try:
            videos.append(probe_video(path))
        except Exception as exc:  # pragma: no cover - diagnostic path
            print(f"[WARN] No se pudo inspeccionar {path.name}: {exc}", file=sys.stderr)
    return videos


def write_inventory(source_dir: Path, output_json: Path) -> None:
    inventory = []
    for info in inventory_videos(source_dir):
        target_width, target_height = compute_target_dimensions(info.width, info.height)
        inventory.append(
            {
                "filename": info.path.name,
                "width": info.width,
                "height": info.height,
                "fps": round(info.fps, 6),
                "duration": round(info.duration, 3),
                "codec_name": info.codec_name,
                "pix_fmt": info.pix_fmt,
                "has_audio": info.has_audio,
                "target_width": target_width,
                "target_height": target_height,
            }
        )
    ensure_parent(output_json)
    output_json.write_text(json.dumps(inventory, indent=2), encoding="utf-8")
    print(f"Inventario guardado en {output_json}")


def github_json(url: str) -> dict[str, Any]:
    request = urllib.request.Request(url, headers={"User-Agent": "video_enhancer_4k"})
    with urllib.request.urlopen(request) as response:
        return json.loads(response.read().decode("utf-8"))


def find_release_asset(repo: str, asset_name_suffix: str, name_contains: str | None = None) -> tuple[str, str]:
    payload = github_json(GITHUB_API.format(repo=repo))
    releases: list[dict[str, Any]]
    if isinstance(payload, dict):
        releases = [payload]
    else:
        releases = payload

    if not any(
        asset["name"].endswith(asset_name_suffix) and (name_contains is None or name_contains in asset["name"])
        for release in releases
        for asset in release.get("assets", [])
    ):
        extra_payload = github_json(GITHUB_RELEASES_API.format(repo=repo))
        releases = extra_payload if isinstance(extra_payload, list) else [extra_payload]

    for release in releases:
        for asset in release.get("assets", []):
            name = asset["name"]
            if name.endswith(asset_name_suffix) and (name_contains is None or name_contains in name):
                return name, asset["browser_download_url"]
    raise RuntimeError(f"No se encontro un asset que termine en {asset_name_suffix!r} para {repo}")


def download_file(url: str, destination: Path) -> Path:
    ensure_parent(destination)
    if destination.exists():
        print(f"Reutilizando descarga: {destination}")
        return destination
    print(f"Descargando {url}")
    request = urllib.request.Request(url, headers={"User-Agent": "video_enhancer_4k"})
    with urllib.request.urlopen(request) as response, destination.open("wb") as handle:
        shutil.copyfileobj(response, handle)
    return destination


def extract_zip(archive: Path, destination: Path) -> None:
    destination.mkdir(parents=True, exist_ok=True)
    marker = destination / ".extracted"
    if marker.exists():
        print(f"Reutilizando extraccion: {destination}")
        return
    with zipfile.ZipFile(archive) as zf:
        zf.extractall(destination)
    marker.write_text("ok", encoding="utf-8")


def find_file(directory: Path, pattern: str) -> Path:
    matches = list(directory.rglob(pattern))
    if not matches:
        raise RuntimeError(f"No se encontro {pattern} dentro de {directory}")
    return matches[0]


def find_realesrgan_executable(directory: Path) -> Path:
    for exe in directory.rglob("realesrgan-ncnn-vulkan.exe"):
        if (exe.parent / "models").exists():
            return exe
    raise RuntimeError(f"No se encontro una instalacion valida de Real-ESRGAN en {directory}")


def ensure_realesrgan() -> Path:
    tool_dir = BIN_DIR / "realesrgan-ncnn-vulkan"
    try:
        return find_realesrgan_executable(tool_dir)
    except RuntimeError:
        pass
    asset_name, download_url = find_release_asset(
        REAL_ESRGAN_REPO,
        "windows.zip",
        name_contains="realesrgan-ncnn-vulkan",
    )
    archive = download_file(download_url, BIN_DIR / asset_name)
    if tool_dir.exists():
        shutil.rmtree(tool_dir)
    extract_zip(archive, tool_dir)
    return find_realesrgan_executable(tool_dir)


def ensure_rife() -> Path:
    tool_dir = BIN_DIR / "rife-ncnn-vulkan"
    try:
        return find_file(tool_dir, "rife-ncnn-vulkan.exe")
    except RuntimeError:
        pass
    asset_name, download_url = find_release_asset(RIFE_REPO, "windows.zip")
    archive = download_file(download_url, BIN_DIR / asset_name)
    extract_zip(archive, tool_dir)
    return find_file(tool_dir, "rife-ncnn-vulkan.exe")


def prepare_tools(tool: str) -> None:
    if tool in {"realesrgan", "all"}:
        exe = ensure_realesrgan()
        print(f"Real-ESRGAN listo en {exe}")
    if tool in {"rife", "all"}:
        exe = ensure_rife()
        print(f"RIFE listo en {exe}")


def extract_frames(source: Path, frames_dir: Path, start: float, duration: float) -> None:
    frames_dir.mkdir(parents=True, exist_ok=True)
    command = [
        "ffmpeg",
        "-y",
        "-ss",
        str(start),
        "-t",
        str(duration),
        "-i",
        str(source),
        "-vsync",
        "0",
        str(frames_dir / "%08d.png"),
    ]
    run(command)


def extract_audio(source: Path, audio_path: Path, start: float, duration: float) -> None:
    command = [
        "ffmpeg",
        "-y",
        "-ss",
        str(start),
        "-t",
        str(duration),
        "-i",
        str(source),
        "-vn",
        "-ar",
        "48000",
        "-c:a",
        "aac",
        "-b:a",
        "192k",
        str(audio_path),
    ]
    run(command)


def upscale_frames_realesrgan(input_dir: Path, output_dir: Path, model: str, scale: int, tile_size: int) -> None:
    exe = ensure_realesrgan()
    models_dir = exe.parent / "models"
    output_dir.mkdir(parents=True, exist_ok=True)
    command = [
        str(exe),
        "-i",
        str(input_dir.resolve()),
        "-o",
        str(output_dir.resolve()),
        "-m",
        str(models_dir.resolve()),
        "-n",
        model,
        "-s",
        str(scale),
        "-t",
        str(tile_size),
        "-j",
        "1:1:1",
        "-v",
    ]
    run(command, cwd=exe.parent)


def interpolate_frames_rife(input_dir: Path, output_dir: Path, uhd: bool) -> None:
    exe = ensure_rife()
    output_dir.mkdir(parents=True, exist_ok=True)
    command = [
        str(exe),
        "-i",
        str(input_dir.resolve()),
        "-o",
        str(output_dir.resolve()),
        "-j",
        "1:1:1",
    ]
    if uhd:
        command.append("-u")
    run(command, cwd=exe.parent)


def encode_frames(
    frames_dir: Path,
    audio_path: Path | None,
    output_path: Path,
    fps: float,
    target_width: int,
    target_height: int,
) -> None:
    ensure_parent(output_path)
    command = [
        "ffmpeg",
        "-y",
        "-framerate",
        f"{fps:.6f}",
        "-i",
        str(frames_dir / "%08d.png"),
    ]
    if audio_path and audio_path.exists():
        command += ["-i", str(audio_path)]
    command += [
        "-vf",
        f"scale={target_width}:{target_height}:flags=lanczos,format=yuv420p",
        "-c:v",
        "libx264",
        "-preset",
        "slow",
        "-crf",
        "17",
        "-profile:v",
        "high",
        "-movflags",
        "+faststart",
        "-colorspace",
        "bt709",
        "-color_primaries",
        "bt709",
        "-color_trc",
        "bt709",
    ]
    if audio_path and audio_path.exists():
        command += [
            "-map",
            "0:v:0",
            "-map",
            "1:a:0",
            "-c:a",
            "aac",
            "-b:a",
            "192k",
            "-ar",
            "48000",
        ]
    else:
        command += ["-an"]
    command.append(str(output_path))
    run(command)


def encode_ffmpeg_lanczos(source: Path, output_path: Path, start: float, duration: float, target_width: int, target_height: int) -> None:
    ensure_parent(output_path)
    command = [
        "ffmpeg",
        "-y",
        "-ss",
        str(start),
        "-t",
        str(duration),
        "-i",
        str(source),
        "-vf",
        f"scale={target_width}:{target_height}:flags=lanczos,format=yuv420p",
        "-c:v",
        "libx264",
        "-preset",
        "slow",
        "-crf",
        "17",
        "-profile:v",
        "high",
        "-movflags",
        "+faststart",
        "-c:a",
        "aac",
        "-b:a",
        "192k",
        "-ar",
        "48000",
        "-colorspace",
        "bt709",
        "-color_primaries",
        "bt709",
        "-color_trc",
        "bt709",
        str(output_path),
    ]
    run(command)


def choose_scale(info: VideoInfo, target_width: int, target_height: int) -> int:
    width_scale = target_width / info.width
    height_scale = target_height / info.height
    desired_scale = max(width_scale, height_scale)
    if desired_scale <= 2:
        return 2
    if desired_scale <= 3:
        return 3
    return 4


def write_report(output_dir: Path, source: Path, engine: str, output_path: Path, info: VideoInfo, target_width: int, target_height: int) -> None:
    report = {
        "source": str(source),
        "engine": engine,
        "output": str(output_path),
        "source_width": info.width,
        "source_height": info.height,
        "source_fps": round(info.fps, 6),
        "duration_seconds": round(info.duration, 3),
        "target_width": target_width,
        "target_height": target_height,
    }
    report_path = output_dir / "report.json"
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"Reporte guardado en {report_path}")


def test_clip(args: argparse.Namespace) -> None:
    source = Path(args.source)
    output_dir = Path(args.output_dir)
    work_dir = output_dir / "work"
    frames_in = work_dir / "frames_in"
    frames_up = work_dir / "frames_up"
    frames_interp = work_dir / "frames_interp"
    audio_path = work_dir / "audio.m4a"

    if output_dir.exists() and args.clean:
        shutil.rmtree(output_dir)
    work_dir.mkdir(parents=True, exist_ok=True)

    info = probe_video(source)
    target_width, target_height = compute_target_dimensions(info.width, info.height, args.target_vertical)
    output_path = output_dir / f"{source.stem}_{args.engine}_{target_height}p.mp4"

    if args.engine == "ffmpeg-lanczos":
        encode_ffmpeg_lanczos(source, output_path, args.start, args.duration, target_width, target_height)
        write_report(output_dir, source, args.engine, output_path, info, target_width, target_height)
        return

    extract_frames(source, frames_in, args.start, args.duration)
    if info.has_audio:
        extract_audio(source, audio_path, args.start, args.duration)
    else:
        audio_path = None

    scale = choose_scale(info, target_width, target_height)
    upscale_frames_realesrgan(frames_in, frames_up, args.model, scale, args.tile_size)

    encode_dir = frames_up
    fps = info.fps

    if args.interpolate:
        interpolate_frames_rife(frames_up, frames_interp, uhd=target_height >= 2160)
        encode_dir = frames_interp
        fps = info.fps * 2

    encode_frames(encode_dir, audio_path, output_path, fps, target_width, target_height)
    write_report(output_dir, source, args.engine, output_path, info, target_width, target_height)


def batch_process(args: argparse.Namespace) -> None:
    source_dir = Path(args.source_dir)
    output_dir = Path(args.output_dir)
    videos = inventory_videos(source_dir)
    for info in videos:
        per_output = output_dir / info.path.stem
        namespace = argparse.Namespace(
            source=str(info.path),
            output_dir=str(per_output),
            engine=args.engine,
            duration=min(args.duration, info.duration),
            start=args.start,
            target_vertical=args.target_vertical,
            model=args.model,
            tile_size=args.tile_size,
            interpolate=args.interpolate,
            clean=args.clean,
        )
        test_clip(namespace)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Mejora videos locales para YouTube con IA o FFmpeg.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    inventory_parser = subparsers.add_parser("inventory", help="Inspecciona videos con ffprobe.")
    inventory_parser.add_argument("--source-dir", default=str(DEFAULT_SOURCE_DIR))
    inventory_parser.add_argument("--output-json", default=str(SAMPLES_DIR / "inventory.json"))

    tools_parser = subparsers.add_parser("prepare-tools", help="Descarga herramientas portables oficiales.")
    tools_parser.add_argument("--tool", choices=["realesrgan", "rife", "all"], default="all")

    shared_parent = argparse.ArgumentParser(add_help=False)
    shared_parent.add_argument("--engine", choices=["realesrgan-ncnn", "ffmpeg-lanczos"], default="ffmpeg-lanczos")
    shared_parent.add_argument("--start", type=float, default=0.0)
    shared_parent.add_argument("--duration", type=float, default=3.0)
    shared_parent.add_argument("--target-vertical", type=int, default=2160)
    shared_parent.add_argument(
        "--model",
        choices=["realesrgan-x4plus", "realesrgan-x4plus-anime", "realesr-animevideov3"],
        default="realesrgan-x4plus",
    )
    shared_parent.add_argument("--tile-size", type=int, default=128)
    shared_parent.add_argument("--interpolate", action="store_true")
    shared_parent.add_argument("--clean", action="store_true")

    test_parser = subparsers.add_parser("test-clip", help="Procesa un clip corto.", parents=[shared_parent])
    test_parser.add_argument("--source", required=True)
    test_parser.add_argument("--output-dir", default=str(SAMPLES_DIR / "test_clip"))

    batch_parser = subparsers.add_parser("batch", help="Procesa todos los mp4 de una carpeta.", parents=[shared_parent])
    batch_parser.add_argument("--source-dir", default=str(DEFAULT_SOURCE_DIR))
    batch_parser.add_argument("--output-dir", default=str(SAMPLES_DIR / "batch"))

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    if args.command == "inventory":
        write_inventory(Path(args.source_dir), Path(args.output_json))
        return
    if args.command == "prepare-tools":
        prepare_tools(args.tool)
        return
    if args.command == "test-clip":
        test_clip(args)
        return
    if args.command == "batch":
        batch_process(args)
        return
    parser.error(f"Comando no soportado: {args.command}")


if __name__ == "__main__":
    main()
