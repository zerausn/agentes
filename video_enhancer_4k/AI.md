# video_enhancer_4k - AI Instructions

Este subproyecto existe para investigar, automatizar y probar mejora local de
video orientada a YouTube, con foco en upscaling a 4K desde material 1080p.

## Objetivo operativo

- Tomar videos locales desde una carpeta externa del usuario.
- Mejorarlos sin depender de servicios cloud.
- Generar salidas listas para subir a YouTube.
- Mantener una ruta portable para Windows 11 con GPU Intel Iris Xe.

## Estado esperado

- Ruta principal: `Real-ESRGAN-ncnn-vulkan`
- Ruta fallback: `FFmpeg Lanczos`
- Ruta opcional futura: `RIFE-ncnn-vulkan` para interpolacion

## Restricciones

- No tocar `youtube_uploader/` salvo que el usuario lo pida explicitamente.
- No asumir CUDA ni NVIDIA.
- Evitar dependencias Python pesadas si existe una alternativa portable.
