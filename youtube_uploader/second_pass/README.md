# Second Pass - Clipping Local para YouTube

Este carril es la **segunda jornada** del `youtube_uploader`.

## Regla de diseno

- **Jornada 1:** subir el material fuente tal como esta con `uploader.py`.
- **Jornada 2:** analizar, recortar, subtitular y empaquetar clips derivados localmente.

La segunda jornada no toca el flujo base. Los optimizados se renderizan en una
carpeta separada y solo entran al indice cuando se registran de forma explicita.

## Que hace `local_clip_optimizer.py`

- normaliza VFR a CFR cuando hace falta
- detecta cambios de escena
- detecta silencios y transiciones negras
- intenta detectar un crop activo para quitar barras
- lee subtitulos o transcript sidecar si existe `.srt`, `.vtt` o `.json`
- puntua ventanas candidatas con enfasis en hook temprano
- renderiza derivados en vertical o teaser cuadrado
- genera manifests y colas de la jornada 2

## Flujo recomendado

1. Jornada 1:

```powershell
python video_scanner.py
python classify_local_videos.py
python uploader.py
```

2. Jornada 2:

```powershell
python second_pass/local_clip_optimizer.py `
  --input "C:\ruta\video.mp4" `
  --render-top 1 `
  --emit-queues `
  --presets youtube_short_hook youtube_short_standard

python second_pass/register_optimized_videos.py `
  --queue second_pass/queues/pendientes_second_pass_hook_shorts.json

python uploader.py
```
