# Second Pass - Clipping y Optimizacion Local

Este carril es la **segunda jornada** del `meta_uploader`.

## Regla de diseno

- **Jornada 1:** subir los videos como estan, usando el uploader actual.
- **Jornada 2:** analizar, recortar, subtitular y adaptar videos localmente
  antes de publicarlos.

Este directorio existe para que las mejoras de clipping **no modifiquen el
flujo base** del uploader.

## Que hace

`local_clip_optimizer.py` analiza videos locales con `ffprobe` y `ffmpeg` para:

- normalizar opcionalmente VFR -> CFR
- detectar cambios de escena
- detectar silencios
- detectar segmentos negros
- puntuar ventanas de atencion
- renderizar clips verticales o cuadrados
- generar colas locales separadas para la segunda jornada

## Colas locales que puede emitir

- `second_pass/queues/pendientes_reels_second_pass.json`
- `second_pass/queues/pendientes_ig_stories_second_pass.json`

## Preparador de segunda jornada desde colas crudas

`prepare_second_jornada_meta.py` toma material de las colas crudas del
uploader y deja lista la segunda jornada sin tocar originales:

- lee `pendientes_posts.json` y/o `pendientes_reels.json`
- prioriza por peso
- renderiza derivados `shared_reel` e `instagram_story`
- acumula las colas locales de segunda jornada sin sobrescribirlas por video
- puede fusionar los derivados reel dentro de `pendientes_reels.json` solo
  cuando lo pidas de forma explicita

Ejemplo seguro, sin tocar la cola principal:

```powershell
python second_pass/prepare_second_jornada_meta.py `
  --source-queues posts `
  --start-index 0 `
  --limit 3 `
  --render-top 1
```

Ejemplo con promocion explicita a la cola principal de reels:

```powershell
python second_pass/prepare_second_jornada_meta.py `
  --source-queues posts `
  --limit 3 `
  --render-top 1 `
  --sync-main-reels-queue
```

## Ejemplos

Analizar un video y renderizar el mejor clip para Reel e IG Story:

```powershell
python second_pass/local_clip_optimizer.py `
  --input "C:\ruta\video.mp4" `
  --render-top 1 `
  --emit-queues
```

Procesar una carpeta y priorizar por archivos mas pesados:

```powershell
python second_pass/local_clip_optimizer.py `
  --input-dir "C:\ruta\videos" `
  --limit 5 `
  --render-top 1 `
  --emit-queues
```

## Artefactos

- `second_pass/manifests/`: reportes JSON por video
- `second_pass/normalized/`: copias normalizadas a CFR cuando haga falta
- `second_pass/optimized_videos/`: clips renderizados
- `second_pass/queues/`: colas separadas de la jornada 2

Todos esos artefactos quedan fuera de Git.
