# PROGRESS - video_enhancer_4k

## 2026-04-20

- Se creo el subproyecto `video_enhancer_4k` dentro de `agentes/`.
- Se eligio como primera ruta realista para esta maquina:
  `Real-ESRGAN-ncnn-vulkan`.
- Se definio un fallback seguro con `ffmpeg` usando `Lanczos`.
- Se inventariaron `53` videos fuente en
  `/media/zerausn/D69493CF9493B08B/Users/ZN-/Documents\ADM\Nueva carpeta`.
- Se descargaron y dejaron listos los binarios portables oficiales de
  `Real-ESRGAN-ncnn-vulkan` y `RIFE-ncnn-vulkan`.
- Se valido una microprueba IA terminada en
  `samples/test_clip_ai_anime_model/video_20240621_182121_realesrgan-ncnn_2160p.mp4`.
- Se valido una prueba practica 4K con fallback en
  `samples/test_clip_lanczos/video_20240621_182121_ffmpeg-lanczos_2160p.mp4`.
- Se comprobo que `realesrgan-x4plus` en `Intel Iris Xe` es demasiado lento
  para batch productivo en esta maquina.
