# DECISIONS - video_enhancer_4k

## 2026-04-20: Priorizar ncnn + Vulkan sobre PyTorch

- Contexto: la maquina actual usa `Intel Iris Xe` y no tiene NVIDIA.
- Decision: la ruta principal queda basada en binarios portables
  `Real-ESRGAN-ncnn-vulkan` y `RIFE-ncnn-vulkan`.
- Consecuencia: se evita depender de CUDA y de entornos PyTorch pesados para la
  primera version operativa.

## 2026-04-20: Mantener fallback con FFmpeg

- Contexto: el upscaling IA puede fallar por drivers, Vulkan o tiempo de
  proceso.
- Decision: el proyecto siempre debe ofrecer una ruta de salida usando solo
  `ffmpeg` con `Lanczos`.
- Consecuencia: el usuario puede producir un master 4K limpio aun cuando la IA
  no sea estable en una maquina dada.

## 2026-04-20: Default operativo en esta Iris Xe = FFmpeg Lanczos

- Contexto: la prueba real mostro que `realesrgan-x4plus` es viable
  tecnicamente, pero demasiado lento para lote en esta iGPU.
- Decision: el motor por defecto del CLI queda en `ffmpeg-lanczos`, mientras la
  ruta `realesrgan-ncnn` queda como experimental y de prueba corta.
- Consecuencia: el proyecto prioriza throughput real para YouTube en esta
  maquina, sin cerrar la puerta a una futura ruta IA mejor adaptada a Intel
  como `OpenVINO` o `vs-mlrt`.
