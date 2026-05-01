# Contexto del Proyecto - video_enhancer_4k

## Que es

Laboratorio operativo para mejorar videos locales antes de subirlos a YouTube,
con prioridad en:

1. Upscaling a 4K.
2. Restauracion ligera.
3. Compatibilidad con Windows 11 e Intel Iris Xe.

## Carpeta fuente del usuario

- Entrada principal:
  `/media/zerausn/D69493CF9493B08B/Users/ZN-/Documents\ADM\Nueva carpeta`

## Decisiones actuales

- Se prefieren binarios portables oficiales sobre entornos PyTorch pesados.
- La primera ruta a validar es `Real-ESRGAN-ncnn-vulkan`.
- El fallback debe funcionar incluso sin Vulkan, usando solo `ffmpeg`.

## Riesgos

- El upscaling por IA en iGPU puede tardar bastante.
- Algunos modelos pueden introducir detalle falso u oversharpening.
- YouTube recomprime; conviene priorizar una salida limpia y estable sobre una
  exageradamente agresiva.
