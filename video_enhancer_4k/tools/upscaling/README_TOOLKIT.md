# 🎬 Upscaling Toolkit — CPU (Linux & Windows)

Tres herramientas para upscaling de fotos y video, sin GPU NVIDIA.

---

## 📦 Estructura

```
upscaling_toolkit/
├── README.md
├── setup/
│   ├── install_linux.sh        # Instalación en Parrot OS / Debian
│   └── install_windows.ps1     # Instalación en Windows (PowerShell)
├── scripts/
│   ├── upscale_photos.py       # Fotos con Real-ESRGAN (PyTorch CPU)
│   ├── upscale_video_ai.py     # Video con Real-ESRGAN NCNN + FFmpeg
│   └── upscale_video_fast.py   # Video rápido con FFmpeg algorítmico
```

---

## 🚀 Flujo de instalación

### Linux (Parrot OS / Debian)
```bash
chmod +x setup/install_linux.sh
./setup/install_linux.sh
```

### Windows (PowerShell como administrador)
```powershell
Set-ExecutionPolicy RemoteSigned -Scope CurrentUser
.\setup\install_windows.ps1
```

---

## 🖼️ 1. Upscaling de FOTOS — Real-ESRGAN (IA, lento pero calidad máxima)

```bash
python scripts/upscale_photos.py -i foto.jpg -o resultado/ -s 4
```

| Parámetro | Descripción | Valores |
|-----------|-------------|---------|
| `-i` | Imagen o carpeta de entrada | ruta/archivo.jpg o ruta/carpeta/ |
| `-o` | Carpeta de salida | ruta/salida/ |
| `-s` | Factor de escala | 2, 4 (default: 4) |
| `--model` | Modelo a usar | general, face, anime (default: general) |

**Ejemplo batch (carpeta completa):**
```bash
python scripts/upscale_photos.py -i ./mis_fotos/ -o ./fotos_4k/ -s 4 --model general
```

---

## 🎬 2. Upscaling de VIDEO con IA — Real-ESRGAN NCNN + FFmpeg

> ⚠️ CPU-only es lento (~1-5 fps). Para video largo, considera procesar de noche.

```bash
python scripts/upscale_video_ai.py -i video.mp4 -o video_4k.mp4 -s 4
```

| Parámetro | Descripción |
|-----------|-------------|
| `-i` | Video de entrada |
| `-o` | Video de salida |
| `-s` | Factor de escala (2 o 4) |
| `--fps` | FPS de salida (default: igual al original) |
| `--preset` | Calidad FFmpeg: slow, medium, fast (default: medium) |

---

## ⚡ 3. Upscaling de VIDEO RÁPIDO — FFmpeg algorítmico (sin IA)

> Rápido en CPU, sin instalar modelos. Calidad buena pero inferior a IA.

```bash
python scripts/upscale_video_fast.py -i video.mp4 -o video_4k.mp4 -w 3840 -h 2160
```

| Parámetro | Descripción | Valores |
|-----------|-------------|---------|
| `-w` / `-h` | Resolución destino | 3840x2160 (4K), 2560x1440 (2K) |
| `--algo` | Algoritmo de escalado | lanczos (default), spline, bicubic, bilinear |
| `--sharpen` | Aplica nitidez post-escala | flag (sin valor) |
| `--denoise` | Reduce ruido antes de escalar | flag (sin valor) |

**Preset directo a 4K con nitidez:**
```bash
python scripts/upscale_video_fast.py -i video.mp4 -o video_4k.mp4 -w 3840 -h 2160 --algo lanczos --sharpen
```

---

## 📊 Comparativa de métodos

| Método | Calidad | Velocidad CPU | Uso recomendado |
|--------|---------|---------------|-----------------|
| Real-ESRGAN fotos | ⭐⭐⭐⭐⭐ | Lento (seg/img) | Fotos importantes, batch nocturno |
| Real-ESRGAN video | ⭐⭐⭐⭐⭐ | Muy lento (min/seg de video) | Clips cortos (<2 min) |
| FFmpeg lanczos | ⭐⭐⭐ | Muy rápido | Video largo, streaming, producción |

---

## 🗂️ Formatos soportados

- **Fotos:** JPG, PNG, WEBP, BMP, TIFF
- **Video:** MP4, MKV, AVI, MOV, WEBM (cualquier codec que FFmpeg soporte)
