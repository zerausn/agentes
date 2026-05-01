#!/usr/bin/env python3
"""
upscale_photos.py — Upscaling de fotos con Real-ESRGAN (CPU)
=============================================================
Uso:
    python upscale_photos.py -i foto.jpg -o salida/ -s 4
    python upscale_photos.py -i ./fotos/ -o ./fotos_4k/ -s 4 --model face
"""

import argparse
import sys
import os
from pathlib import Path

# ── Verificar dependencias antes de importar ─────────────────────────────────
def check_dependencies():
    missing = []
    for pkg in ["torch", "realesrgan", "PIL", "cv2", "tqdm"]:
        try:
            __import__(pkg if pkg != "PIL" else "PIL.Image")
        except ImportError:
            missing.append(pkg.replace("PIL", "pillow").replace("cv2", "opencv-python-headless"))
    if missing:
        print("[X] Dependencias faltantes:", ", ".join(missing))
        print("  Ejecuta primero: setup/install_linux.sh  o  setup/install_windows.ps1")
        sys.exit(1)

check_dependencies()

import cv2
import torch
import numpy as np
from PIL import Image
from tqdm import tqdm
from basicsr.archs.rrdbnet_arch import RRDBNet
from realesrgan import RealESRGANer

# ── Modelos disponibles ───────────────────────────────────────────────────────
MODELS = {
    "general": {
        "name":    "RealESRGAN_x4plus",
        "url":     "https://github.com/xinntao/Real-ESRGAN/releases/download/v0.1.0/RealESRGAN_x4plus.pth",
        "arch":    RRDBNet(num_in_ch=3, num_out_ch=3, num_feat=64, num_block=23, num_grow_ch=32, scale=4),
        "scale":   4,
        "desc":    "General photos — mejor calidad",
    },
    "face": {
        "name":    "RealESRGAN_x4plus_anime_6B",
        "url":     "https://github.com/xinntao/Real-ESRGAN/releases/download/v0.2.2.4/RealESRGAN_x4plus_anime_6B.pth",
        "arch":    RRDBNet(num_in_ch=3, num_out_ch=3, num_feat=64, num_block=6,  num_grow_ch=32, scale=4),
        "scale":   4,
        "desc":    "Anime / ilustraciones",
    },
}

SUPPORTED_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tiff", ".tif"}


def build_upsampler(model_key: str, scale: int, half: bool = False) -> RealESRGANer:
    """Carga el modelo Real-ESRGAN en modo CPU."""
    cfg = MODELS[model_key]
    model_dir = Path.home() / ".cache" / "realesrgan"
    model_dir.mkdir(parents=True, exist_ok=True)
    model_path = model_dir / f"{cfg['name']}.pth"

    if not model_path.exists():
        print(f"  Descargando modelo '{model_key}' (~65 MB)...")
        import urllib.request
        urllib.request.urlretrieve(cfg["url"], model_path,
            reporthook=lambda c, bs, ts: print(f"\r  {min(c*bs, ts)/1e6:.1f}/{ts/1e6:.1f} MB", end=""))
        print()

    upsampler = RealESRGANer(
        scale      = cfg["scale"],
        model_path = str(model_path),
        model      = cfg["arch"],
        tile       = 256,           # procesa en tiles para no agotar RAM en CPU
        tile_pad   = 10,
        pre_pad    = 0,
        half       = False,         # CPU no soporta half-precision
        device     = torch.device("cpu"),
    )
    return upsampler


def upscale_image(path_in: Path, path_out: Path, upsampler: RealESRGANer, scale: int):
    """Escala una imagen y la guarda."""
    img = cv2.imread(str(path_in), cv2.IMREAD_UNCHANGED)
    if img is None:
        print(f"  ⚠ No se pudo leer: {path_in.name}")
        return False

    h, w = img.shape[:2]
    output, _ = upsampler.enhance(img, outscale=scale)

    # Preservar alpha si la imagen original lo tiene
    if img.shape[2] == 4 and output.shape[2] == 3:
        alpha = cv2.resize(img[:, :, 3], (output.shape[1], output.shape[0]),
                           interpolation=cv2.INTER_LANCZOS4)
        output = cv2.merge([output[:, :, 0], output[:, :, 1],
                            output[:, :, 2], alpha])

    # Mantener extensión original (PNG preserva lossless)
    ext = path_out.suffix.lower()
    if ext in {".jpg", ".jpeg"}:
        cv2.imwrite(str(path_out), output, [cv2.IMWRITE_JPEG_QUALITY, 95])
    elif ext == ".png":
        cv2.imwrite(str(path_out), output, [cv2.IMWRITE_PNG_COMPRESSION, 1])
    else:
        cv2.imwrite(str(path_out), output)

    h_out, w_out = output.shape[:2]
    print(f"  [OK] {path_in.name}  [{w}x{h}] -> [{w_out}x{h_out}]")
    return True


def collect_images(input_path: Path) -> list[Path]:
    if input_path.is_file():
        return [input_path] if input_path.suffix.lower() in SUPPORTED_EXTS else []
    return sorted([p for p in input_path.rglob("*") if p.suffix.lower() in SUPPORTED_EXTS])


def main():
    parser = argparse.ArgumentParser(
        description="Upscaling de fotos con Real-ESRGAN (CPU)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Ejemplos:
  python upscale_photos.py -i foto.jpg -o salida/ -s 4
  python upscale_photos.py -i ./fotos/ -o ./fotos_4k/ -s 4 --model face
  python upscale_photos.py -i img.png  -o salida/ -s 2
        """
    )
    parser.add_argument("-i",  "--input",  required=True,  help="Imagen o carpeta de entrada")
    parser.add_argument("-o",  "--output", required=True,  help="Carpeta de salida")
    parser.add_argument("-s",  "--scale",  type=int, default=4, choices=[2, 4],
                        help="Factor de escala: 2 o 4 (default: 4)")
    parser.add_argument("--model", default="general", choices=list(MODELS.keys()),
                        help="Modelo: general | face (default: general)")
    parser.add_argument("--suffix", default="_4k",
                        help="Sufijo añadido al nombre del archivo (default: _4k)")
    args = parser.parse_args()

    path_in  = Path(args.input)
    path_out = Path(args.output)

    if not path_in.exists():
        print(f"No existe: {path_in}")
        sys.exit(1)

    path_out.mkdir(parents=True, exist_ok=True)
    images = collect_images(path_in)

    if not images:
        print(f"No se encontraron imágenes en: {path_in}")
        print(f"  Extensiones soportadas: {', '.join(SUPPORTED_EXTS)}")
        sys.exit(1)

    print(f"\n{'='*50}")
    print(f"  Real-ESRGAN Upscaler (CPU)")
    print(f"  Modelo : {args.model} — {MODELS[args.model]['desc']}")
    print(f"  Escala : ×{args.scale}")
    print(f"  Imágenes: {len(images)}")
    print(f"{'='*50}\n")
    print("  Cargando modelo...")

    upsampler = build_upsampler(args.model, args.scale)

    ok, fail = 0, 0
    for img_path in tqdm(images, desc="Procesando", unit="img"):
        # Reconstruir ruta de salida preservando subdirectorios si es carpeta
        if path_in.is_dir():
            rel = img_path.relative_to(path_in)
            out_path = path_out / rel.with_stem(rel.stem + args.suffix)
        else:
            out_path = path_out / (img_path.stem + args.suffix + img_path.suffix)
        out_path.parent.mkdir(parents=True, exist_ok=True)

        try:
            if upscale_image(img_path, out_path, upsampler, args.scale):
                ok += 1
            else:
                fail += 1
        except Exception as e:
            print(f"  Error en {img_path.name}: {e}")
            fail += 1

    print(f"\n{'='*50}")
    print(f"  Completado: {ok} OK  |  {fail} errores")
    print(f"  Salida: {path_out.resolve()}")
    print(f"{'='*50}\n")


if __name__ == "__main__":
    main()
