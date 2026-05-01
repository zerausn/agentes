# video_enhancer_4k

Pipeline local para mejorar videos orientados a YouTube desde Windows 11.

## Objetivo

Tomar videos locales, analizarlos, generar una prueba corta y luego procesarlos
por lote con una de estas rutas:

- `realesrgan-ncnn`: upscaling por IA con Vulkan, portable y apto para Intel.
- `ffmpeg-lanczos`: fallback rapido sin IA.
- `rife-ncnn`: interpolacion opcional para subir FPS.

## Por que esta ruta

En esta maquina hay `Intel Iris Xe`, `ffmpeg` y `python`, pero no hay NVIDIA.
Por eso la ruta mas practica para validar IA real es `ncnn-vulkan`, no
PyTorch/CUDA.

## Estado real en esta maquina

- `ffmpeg-lanczos`: validado y util para producir masters 4K completos.
- `realesrgan-ncnn` con `realesrgan-x4plus`: funcional, pero demasiado lento
  para lote en `Intel Iris Xe`.
- `realesrgan-ncnn` con `realesr-animevideov3`: validado sobre una microprueba,
  pero no es el modelo recomendado para video real de camara.

## Uso rapido

### 1. Inventario de la carpeta fuente

```powershell
python enhance_videos.py inventory `
  --source-dir "/media/zerausn/D69493CF9493B08B/Users/ZN-/Documents\ADM\Nueva carpeta" `
  --output-json ".\samples\inventory.json"
```

### 2. Descargar herramientas oficiales portables

```powershell
python enhance_videos.py prepare-tools --tool all
```

### 3. Procesar una prueba corta a 4K con IA experimental

```powershell
python enhance_videos.py test-clip `
  --source "/media/zerausn/D69493CF9493B08B/Users/ZN-/Documents\ADM\Nueva carpeta\video_20240621_182121.mp4" `
  --engine realesrgan-ncnn `
  --duration 3 `
  --target-vertical 2160 `
  --output-dir ".\samples\test_clip"
```

### 4. Procesar por lote con fallback rapido

```powershell
python enhance_videos.py batch `
  --source-dir "/media/zerausn/D69493CF9493B08B/Users/ZN-/Documents\ADM\Nueva carpeta" `
  --output-dir ".\samples\batch_lanczos"
```

## Recomendaciones practicas

- Para tus videos `1080p` reales, prueba primero `realesrgan-x4plus`.
- Para material anime o ilustrado, usa `realesrgan-x4plus-anime` o
  `realesr-animevideov3`.
- Para YouTube SDR, este proyecto codifica en `MP4 + H.264 + AAC + faststart`
  con color `BT.709`.
- En esta Iris Xe, el camino operativo recomendado por defecto es
  `ffmpeg-lanczos`; deja la IA para pruebas cortas o futuras mejoras con
## 📥 Herramientas integradas (Upscaling Toolkit)

Se ha integrado el toolkit del escritorio para procesamiento directo:

- `tools/upscaling/scripts/upscale_photos.py`: Mejora fotos con IA (PyTorch).
- `tools/upscaling/scripts/upscale_video_ai.py`: Mejora video con IA (NCNN).
- `tools/upscaling/scripts/upscale_video_fast.py`: Mejora video rápido (FFmpeg).

### Uso del entorno local:
```powershell
# Activar entorno
.\.venv\Scripts\activate
# Ejecutar herramienta
python tools\upscaling\scripts\upscale_video_fast.py --help
```

---

## Estructura

- `enhance_videos.py`: CLI principal.
- `tools/`: herramientas adicionales e integraciones.
- `bin/`: herramientas portables descargadas (incluye realesrgan-ncnn).
- `samples/`: inventarios y pruebas.
- `docs/`: memoria del subproyecto.
- `tests/`: pruebas unitarias ligeras.
