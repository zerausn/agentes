#!/usr/bin/env python3
"""
upscale_video_ai.py — Upscaling de video con Real-ESRGAN NCNN + FFmpeg (CPU)
=============================================================================
Proceso:
  1. FFmpeg extrae frames del video
  2. Real-ESRGAN NCNN escala cada frame (usa Vulkan, funciona en CPU)
  3. FFmpeg reensambla los frames al video final con el audio original

Uso:
    python upscale_video_ai.py -i video.mp4 -o video_4k.mp4 -s 4
    python upscale_video_ai.py -i clip.mkv  -o clip_4k.mp4  -s 2 --preset slow

⚠ ADVERTENCIA CPU: ~1–3 fps de procesamiento. Para 1 min de video a 30fps
  son ~600 frames. Puede tardar 30–60 minutos en CPU potente.
  Usa upscale_video_fast.py si necesitas velocidad.
"""

import argparse
import subprocess
import sys
import os
import shutil
import tempfile
from pathlib import Path
import json


# ── Utilidades ────────────────────────────────────────────────────────────────

def run(cmd: list, desc: str = "", check: bool = True) -> subprocess.CompletedProcess:
    """Ejecuta un comando mostrando la descripción."""
    if desc:
        print(f"  → {desc}")
    return subprocess.run(cmd, check=check, capture_output=True, text=True)


def find_binary(name: str, fallback_dirs: list[str]) -> str | None:
    """Busca un binario en PATH y en directorios de fallback."""
    if shutil.which(name):
        return shutil.which(name)
    for d in fallback_dirs:
        candidate = Path(d) / name
        if candidate.exists():
            return str(candidate)
        candidate_exe = Path(d) / f"{name}.exe"
        if candidate_exe.exists():
            return str(candidate_exe)
    return None


def get_video_info(video_path: str) -> dict:
    """Obtiene metadatos del video con ffprobe."""
    cmd = [
        "ffprobe", "-v", "quiet", "-print_format", "json",
        "-show_streams", "-show_format", video_path
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, check=True)
    data = json.loads(result.stdout)

    info = {"width": 0, "height": 0, "fps": 30.0, "duration": 0.0, "has_audio": False}
    for stream in data.get("streams", []):
        if stream.get("codec_type") == "video":
            info["width"]  = int(stream.get("width", 0))
            info["height"] = int(stream.get("height", 0))
            fps_str = stream.get("r_frame_rate", "30/1")
            num, den = map(int, fps_str.split("/"))
            info["fps"] = round(num / den, 3)
        elif stream.get("codec_type") == "audio":
            info["has_audio"] = True
    info["duration"] = float(data.get("format", {}).get("duration", 0))
    return info


# ── Pipeline principal ────────────────────────────────────────────────────────

def extract_frames(video_path: str, frames_dir: Path, fps: float):
    """Extrae todos los frames del video como PNG."""
    print(f"  Extrayendo frames (fps={fps})...")
    cmd = [
        "ffmpeg", "-y", "-i", video_path,
        "-vf", f"fps={fps}",
        "-q:v", "1",
        str(frames_dir / "frame_%08d.png")
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"  ✗ Error extrayendo frames:\n{result.stderr}")
        sys.exit(1)
    frames = sorted(frames_dir.glob("frame_*.png"))
    print(f"  [OK] {len(frames)} frames extraidos")
    return frames


def upscale_frames(frames_dir: Path, upscaled_dir: Path, scale: int, ncnn_bin: str):
    """
    Escala los frames con Real-ESRGAN NCNN.
    El binario procesa una carpeta completa de una vez.
    """
    model = f"realesrgan-x{scale}plus"
    print(f"  Escalando con Real-ESRGAN NCNN (×{scale}, CPU)...")
    print(f"  Modelo: {model}")

    cmd = [
        ncnn_bin,
        "-i", str(frames_dir),
        "-o", str(upscaled_dir),
        "-s", str(scale),
        "-n", model,
        "-f", "png",
        "-j", "1:1:1",   # 1 hilo IO / 1 proc / 1 hilo salida — estable en CPU
    ]
    result = subprocess.run(cmd, text=True)
    if result.returncode != 0:
        print(f"  ✗ Error en Real-ESRGAN NCNN (código {result.returncode})")
        print("  Tip: verifica que el binario ncnn esté en la carpeta bin/")
        sys.exit(1)

    upscaled = sorted(upscaled_dir.glob("*.png"))
    print(f"  [OK] {len(upscaled)} frames escalados")


def encode_video(upscaled_dir: Path, output_path: str, original_path: str,
                 fps: float, preset: str, has_audio: bool, crf: int = 18):
    """Reensambla los frames en video y agrega el audio original."""
    print(f"  Codificando video final (preset={preset}, crf={crf})...")

    # 1. Reensamblar frames
    cmd_encode = [
        "ffmpeg", "-y",
        "-framerate", str(fps),
        "-pattern_type", "glob",
        "-i", str(upscaled_dir / "*.png"),
        "-c:v", "libx264",
        "-crf", str(crf),
        "-preset", preset,
        "-pix_fmt", "yuv420p",
    ]

    if has_audio:
        # Agregar audio del original
        cmd_encode += [
            "-i", original_path,
            "-map", "0:v:0",
            "-map", "1:a:0",
            "-c:a", "aac",
            "-b:a", "192k",
            "-shortest",
        ]

    cmd_encode.append(output_path)
    result = subprocess.run(cmd_encode, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"  ✗ Error codificando video:\n{result.stderr[-500:]}")
        sys.exit(1)
    print(f"  [OK] Video codificado")


def main():
    parser = argparse.ArgumentParser(
        description="Upscaling de video con IA (Real-ESRGAN NCNN + FFmpeg, CPU)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Ejemplos:
  python upscale_video_ai.py -i video.mp4 -o video_4k.mp4 -s 4
  python upscale_video_ai.py -i clip.mkv  -o clip_4k.mp4  -s 2 --preset slow
  python upscale_video_ai.py -i video.mp4 -o video_4k.mp4 -s 4 --crf 16
        """
    )
    parser.add_argument("-i",  "--input",   required=True, help="Video de entrada")
    parser.add_argument("-o",  "--output",  required=True, help="Video de salida (.mp4)")
    parser.add_argument("-s",  "--scale",   type=int, default=4, choices=[2, 4],
                        help="Factor de escala: 2 o 4 (default: 4)")
    parser.add_argument("--preset", default="medium",
                        choices=["ultrafast","fast","medium","slow","veryslow"],
                        help="Preset de codificación H.264 (default: medium)")
    parser.add_argument("--crf", type=int, default=18,
                        help="Calidad H.264: 0=sin pérdida, 18=alta calidad, 28=ok (default: 18)")
    parser.add_argument("--fps", type=float, default=None,
                        help="FPS del video de salida (default: igual al original)")
    parser.add_argument("--keep-frames", action="store_true",
                        help="Conserva los frames temporales (para debug)")
    args = parser.parse_args()

    path_in  = Path(args.input)
    path_out = Path(args.output)

    if not path_in.exists():
        print(f"✗ No existe: {path_in}")
        sys.exit(1)

    # --- Buscar binarios ---
    ffmpeg_bin = shutil.which("ffmpeg")
    ffprobe_bin = shutil.which("ffprobe")
    if not ffmpeg_bin or not ffprobe_bin:
        print("✗ FFmpeg/ffprobe no encontrado en PATH.")
        sys.exit(1)

    script_dir  = Path(__file__).parent.parent
    project_root = script_dir.parent.parent
    ncnn_dirs   = [
        script_dir / "bin", 
        project_root / "bin",
        Path.home() / "bin", 
        Path("/usr/local/bin")
    ]
    ncnn_name   = "realesrgan-ncnn-vulkan"
    ncnn_bin    = find_binary(ncnn_name, [str(d) for d in ncnn_dirs])

    if not ncnn_bin:
        print(f"✗ No se encontró '{ncnn_name}'.")
        print(f"  Ejecuta setup/install_linux.sh (o install_windows.ps1)")
        print(f"  O descárgalo manualmente de:")
        print(f"  https://github.com/xinntao/Real-ESRGAN/releases")
        sys.exit(1)

    # --- Info del video ---
    print(f"\n{'='*55}")
    print(f"  Real-ESRGAN Video Upscaler (CPU)")
    print(f"{'='*55}")

    info = get_video_info(str(path_in))
    fps  = args.fps or info["fps"]
    mins = int(info["duration"] // 60)
    secs = int(info["duration"] % 60)

    print(f"  Entrada  : {path_in.name}")
    print(f"  Tamaño   : {info['width']}×{info['height']}")
    print(f"  FPS      : {info['fps']}")
    print(f"  Duración : {mins}m {secs}s")
    print(f"  Audio    : {'sí' if info['has_audio'] else 'no'}")
    print(f"  Escala   : ×{args.scale}")
    est_frames = int(info["duration"] * fps)
    print(f"  Frames   : ~{est_frames}")
    print(f"  Tiempo estimado CPU: ~{est_frames // 2}–{est_frames} segundos")
    print(f"{'='*55}\n")

    path_out.parent.mkdir(parents=True, exist_ok=True)

    # --- Directorios temporales ---
    tmp_root    = Path(tempfile.mkdtemp(prefix="upscale_video_"))
    frames_dir  = tmp_root / "frames"
    upscaled_dir = tmp_root / "upscaled"
    frames_dir.mkdir()
    upscaled_dir.mkdir()

    try:
        # Paso 1: extraer frames
        print("[1/3] Extrayendo frames...")
        extract_frames(str(path_in), frames_dir, fps)

        # Paso 2: escalar con IA
        print(f"\n[2/3] Escalando con Real-ESRGAN NCNN...")
        upscale_frames(frames_dir, upscaled_dir, args.scale, ncnn_bin)

        # Paso 3: codificar
        print(f"\n[3/3] Recodificando video final...")
        encode_video(upscaled_dir, str(path_out), str(path_in),
                     fps, args.preset, info["has_audio"], args.crf)

    finally:
        if not args.keep_frames:
            shutil.rmtree(tmp_root, ignore_errors=True)
        else:
            print(f"\n  Frames conservados en: {tmp_root}")

    size_mb = path_out.stat().st_size / 1e6
    print(f"\n[OK] Completado")
    print(f"  Salida: {path_out.resolve()}")
    print(f"  Tamaño: {size_mb:.1f} MB")
    print(f"{'='*55}\n")


if __name__ == "__main__":
    main()
