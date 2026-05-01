#!/usr/bin/env python3
"""
upscale_video_fast.py — Upscaling rápido de video con FFmpeg (sin IA)
======================================================================
Usa algoritmos clásicos de escalado (lanczos, spline, etc.).
Mucho más rápido que IA pero sin reconstrucción de detalle.
Ideal para: videos largos, streaming, producción con tiempo limitado.

Uso:
    python upscale_video_fast.py -i video.mp4 -o video_4k.mp4 -w 3840 -h 2160
    python upscale_video_fast.py -i video.mp4 -o video_4k.mp4 -w 3840 -h 2160 --sharpen
    python upscale_video_fast.py -i video.mp4 -o video_2k.mp4 -w 2560 -h 1440 --denoise --sharpen
"""

import argparse
import subprocess
import sys
import shutil
import json
from pathlib import Path


# ── Presets de resolución ─────────────────────────────────────────────────────
RESOLUTION_PRESETS = {
    "4k":  (3840, 2160),
    "2k":  (2560, 1440),
    "fhd": (1920, 1080),
    "hd":  (1280, 720),
}

# ── Descripción de algoritmos ─────────────────────────────────────────────────
ALGO_DESC = {
    "lanczos":  "Mejor nitidez general — recomendado para la mayoría de casos",
    "spline":   "Suavidad con buen detalle — bueno para movimiento",
    "bicubic":  "Clásico balanceado — compatible con todo",
    "bilinear": "Más rápido, menos detalle",
    "neighbor": "Pixelado (útil solo para pixel art)",
}


def get_video_info(video_path: str) -> dict:
    cmd = [
        "ffprobe", "-v", "quiet", "-print_format", "json",
        "-show_streams", "-show_format", video_path
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, check=True)
    data = json.loads(result.stdout)

    info = {"width": 0, "height": 0, "fps": "30/1", "duration": 0.0,
            "has_audio": False, "vcodec": "h264", "acodec": "aac"}
    for s in data.get("streams", []):
        if s.get("codec_type") == "video":
            info["width"]  = int(s.get("width", 0))
            info["height"] = int(s.get("height", 0))
            info["fps"]    = s.get("r_frame_rate", "30/1")
            info["vcodec"] = s.get("codec_name", "h264")
        elif s.get("codec_type") == "audio":
            info["has_audio"] = True
            info["acodec"]    = s.get("codec_name", "aac")
    info["duration"] = float(data.get("format", {}).get("duration", 0))
    return info


def build_vf_chain(w_out: int, h_out: int, w_in: int, h_in: int,
                   algo: str, sharpen: bool, denoise: bool,
                   deinterlace: bool) -> str:
    """Construye la cadena de filtros de FFmpeg."""
    filters = []

    # Deinterlace (útil para video grabado/TV)
    if deinterlace:
        filters.append("yadif=mode=1")

    # Denoise antes de escalar mejora el resultado
    if denoise:
        filters.append("hqdn3d=4:4:3:3")

    # Escalado principal
    filters.append(f"scale={w_out}:{h_out}:flags={algo}+accurate_rnd+full_chroma_int")

    # Nitidez post-escala (unsharp mask)
    if sharpen:
        filters.append("unsharp=5:5:1.2:5:5:0.0")

    return ",".join(filters)


def estimate_time(duration: float, w_in: int, h_in: int,
                  w_out: int, h_out: int, algo: str) -> str:
    """Estimación muy aproximada de tiempo en CPU moderna."""
    # Pixels por segundo procesados (muy rough)
    algo_speed = {"bilinear": 200, "bicubic": 150, "lanczos": 80,
                  "spline": 70, "neighbor": 400}
    mpix_per_sec = algo_speed.get(algo, 100)  # Megapixels/seg
    total_mpix = duration * 30 * (w_out * h_out / 1e6)
    secs = total_mpix / mpix_per_sec
    if secs < 60:
        return f"~{int(secs)}s"
    elif secs < 3600:
        return f"~{int(secs/60)}m"
    else:
        return f"~{secs/3600:.1f}h"


def main():
    parser = argparse.ArgumentParser(
        description="Upscaling rápido de video con FFmpeg (sin IA, CPU)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Resoluciones frecuentes:
  4K UHD : -w 3840 -h 2160  (o --preset 4k)
  2K QHD : -w 2560 -h 1440  (o --preset 2k)
  FHD    : -w 1920 -h 1080  (o --preset fhd)

Ejemplos:
  python upscale_video_fast.py -i vid.mp4 -o vid_4k.mp4 --preset 4k
  python upscale_video_fast.py -i vid.mp4 -o vid_4k.mp4 -w 3840 -h 2160 --sharpen
  python upscale_video_fast.py -i vid.mp4 -o vid_4k.mp4 --preset 4k --denoise --sharpen --algo spline
  python upscale_video_fast.py -i vid.mp4 -o vid_4k.mp4 --preset 4k --crf 16 --preset-enc slow
        """
    )

    # Resolución
    res_grp = parser.add_mutually_exclusive_group(required=True)
    res_grp.add_argument("-w", "--width",  type=int, help="Ancho de salida en px")
    res_grp.add_argument("--preset",       choices=list(RESOLUTION_PRESETS.keys()),
                         help="Preset de resolución: 4k, 2k, fhd, hd")

    parser.add_argument("-i",  "--input",    required=True, help="Video de entrada")
    parser.add_argument("-o",  "--output",   required=True, help="Video de salida")
    parser.add_argument("--height", "-H",    type=int,      help="Alto de salida (auto si no se especifica)")
    parser.add_argument("--algo",            default="lanczos",
                        choices=list(ALGO_DESC.keys()),
                        help="Algoritmo de escalado (default: lanczos)")
    parser.add_argument("--sharpen",         action="store_true",
                        help="Aplica nitidez post-escala (unsharp mask)")
    parser.add_argument("--denoise",         action="store_true",
                        help="Reduce ruido antes de escalar (hqdn3d)")
    parser.add_argument("--deinterlace",     action="store_true",
                        help="Desentrelaza antes de escalar (para video TV/grabado)")
    parser.add_argument("--crf",             type=int, default=18,
                        help="Calidad H.264 CRF: 0=sin pérdida, 18=alta, 28=ok (default: 18)")
    parser.add_argument("--preset-enc",      default="fast",
                        choices=["ultrafast","superfast","veryfast","faster","fast","medium","slow","veryslow"],
                        dest="preset_enc",
                        help="Preset de codificación (default: fast)")
    parser.add_argument("--copy-audio",      action="store_true", default=True,
                        help="Copiar audio sin re-codificar (default: sí)")
    parser.add_argument("--no-copy-audio",   action="store_false", dest="copy_audio")

    args = parser.parse_args()

    # Resolver dimensiones
    if args.preset:
        w_out, h_out = RESOLUTION_PRESETS[args.preset]
    else:
        w_out = args.width
        h_out = args.height if args.height else -2   # -2 = mantener aspect ratio

    path_in  = Path(args.input)
    path_out = Path(args.output)

    if not path_in.exists():
        print(f"  No existe: {path_in}")
        sys.exit(1)

    if not shutil.which("ffmpeg"):
        print("✗ FFmpeg no encontrado. Instálalo primero.")
        print("FFmpeg no encontrado. Instálalo primero.")
        sys.exit(1)

    # Info del video
    info = get_video_info(str(path_in))
    w_in, h_in = info["width"], info["height"]

    if w_out <= w_in and (h_out == -2 or h_out <= h_in):
        print(f"  LA RESOLUCION DE SALIDA ({w_out}x{h_out}) NO ES MAYOR QUE LA ENTRADA.")
        print("  Continuando de todas formas...")

    mins = int(info["duration"] // 60)
    secs = int(info["duration"] % 60)

    print(f"\n{'='*58}")
    print(f"  FFmpeg Video Upscaler (Algorítmico, sin IA)")
    print(f"{'='*58}")
    print(f"  Entrada   : {path_in.name}")
    print(f"  Resolucion: {w_in}x{h_in}  ->  {w_out}x{h_out if h_out != -2 else 'auto'}")
    print(f"  Duración  : {mins}m {secs}s")
    print(f"  Algoritmo : {args.algo}  ({ALGO_DESC.get(args.algo, '')})")
    print(f"  Nitidez   : {'sí' if args.sharpen else 'no'}")
    print(f"  Denoise   : {'sí' if args.denoise else 'no'}")
    print(f"  CRF       : {args.crf}  |  Preset: {args.preset_enc}")
    est = estimate_time(info["duration"], w_in, h_in, w_out,
                        h_out if h_out != -2 else int(w_out * h_in / w_in),
                        args.algo)
    print(f"  Tiempo est.: {est}")
    print(f"{'='*58}\n")

    # Construir filtros
    vf = build_vf_chain(w_out, h_out, w_in, h_in,
                        args.algo, args.sharpen, args.denoise, args.deinterlace)

    path_out.parent.mkdir(parents=True, exist_ok=True)

    # Construir comando FFmpeg
    cmd = [
        "ffmpeg", "-y",
        "-i", str(path_in),
        "-vf", vf,
        "-c:v", "libx264",
        "-crf", str(args.crf),
        "-preset", args.preset_enc,
        "-pix_fmt", "yuv420p",
    ]

    if info["has_audio"]:
        if args.copy_audio:
            cmd += ["-c:a", "copy"]
        else:
            cmd += ["-c:a", "aac", "-b:a", "192k"]

    cmd.append(str(path_out))

    print(f"  Comando FFmpeg:")
    print(f"  {' '.join(cmd)}\n")
    print("  Procesando...\n")

    # Ejecutar mostrando progreso en tiempo real
    result = subprocess.run(cmd, stderr=subprocess.PIPE, text=True)

    if result.returncode != 0:
        # Mostrar últimas líneas de error
        print(f"\nError en FFmpeg:")
        for line in result.stderr.splitlines()[-15:]:
            print(f"  {line}")
        sys.exit(1)

    size_mb = path_out.stat().st_size / 1e6
    print(f"\n{'='*58}")
    print(f"\n  [OK] Completado")
    print(f"  Salida: {path_out.resolve()}")
    print(f"  Tamaño : {size_mb:.1f} MB")
    print(f"{'='*58}\n")


if __name__ == "__main__":
    main()
