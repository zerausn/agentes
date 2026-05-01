# ARCHITECTURE - video_enhancer_4k

## Flujo principal

1. Inventario con `ffprobe`.
2. Preparacion de herramientas portables desde releases oficiales.
3. Extraccion de frames del clip o video.
4. Upscaling:
   - `realesrgan-ncnn-vulkan`, o
   - `ffmpeg-lanczos`
5. Re-encode a master `MP4/H.264/AAC/BT.709/faststart`.
6. Registro de metadatos del output para futura integracion con YouTube.

## Filosofia

- Hacer primero una prueba corta y medible.
- Mantener un camino de emergencia sin IA.
- Preservar los originales y escribir todo dentro de este subproyecto.
