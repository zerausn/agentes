# Videos Optimizados - Clipping y Optimizacion Local

Este carril es el de **videos optimizados** del `meta_uploader`.

## Regla de diseno

- **Jornada 1:** subir los videos como estan, usando el uploader actual.
- **Videos optimizados:** analizar, recortar, subtitular y adaptar videos
  localmente
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
- generar colas locales separadas para videos optimizados

## Colas locales que puede emitir

- `second_pass/queues/pendientes_reels_second_pass.json`
- `second_pass/queues/pendientes_ig_stories_second_pass.json`

## Preparador de videos optimizados desde colas crudas

`prepare_second_jornada_meta.py` toma material de las colas crudas del
uploader y deja lista la capa de videos optimizados sin tocar originales:

- lee `pendientes_posts.json` y/o `pendientes_reels.json`
- prioriza por peso
- renderiza derivados `shared_reel` e `instagram_story`
- acumula las colas locales de videos optimizados sin sobrescribirlas por video
- puede fusionar los derivados reel dentro de `pendientes_reels.json` solo
  cuando lo pidas de forma explicita

## Transcodificador full-length API-safe para Instagram

`transcode_instagram_api_safe.py` existe para el caso en que un video crudo
publique bien en Facebook pero falle en Instagram por limites del carril API.

Objetivo:

- conservar el video completo, no solo un clip
- bajar el ancho a un maximo compatible
- recalcular bitrate segun la duracion para entrar bajo el limite de tamano
- exportar una version con la maxima calidad posible dentro del marco oficial
  de Instagram Graph API

Que hace:

- reescala a un maximo de `1920` columnas preservando aspect ratio
- transcodifica a `H.264 + AAC`
- usa `two-pass` para acercarse al mejor bitrate posible sin pasarse del
  presupuesto de archivo
- deja un manifest en `second_pass/manifests/`
- opcionalmente acumula una cola separada:
  - `second_pass/queues/pendientes_ig_feed_second_pass.json`

Ejemplo:

```powershell
python second_pass/transcode_instagram_api_safe.py `
  --input "C:\ruta\video.mp4" `
  --emit-queue
```

Ejemplo por carpeta, priorizando los mas pesados:

```powershell
python second_pass/transcode_instagram_api_safe.py `
  --input-dir "C:\ruta\videos" `
  --limit 3 `
  --emit-queue
```

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

## Herramienta experimental YOLO separada

`experimental_yolo_reframer.py` queda totalmente aparte del flujo productivo.
Sirve para probar, antes de integrar nada, si un recorte inteligente 9:16 con
YOLO realmente mejora el material.

Que hace:

- toma un video o segmento puntual
- construye un plan de crop vertical con deteccion de personas
- puede renderizar un clip experimental aparte
- guarda planes JSON y renders bajo `second_pass/outputs/yolo_reframe_experiments/`
- no toca colas de produccion
- no se integra con `run_jornada1_normal.py` ni con `prepare_second_jornada_meta.py`

Ejemplo de plan sin render:

```powershell
python second_pass/experimental_yolo_reframer.py `
  --input "C:\ruta\video.mp4" `
  --start-seconds 0 `
  --duration-seconds 20
```

Ejemplo con render experimental:

```powershell
python second_pass/experimental_yolo_reframer.py `
  --input "C:\ruta\video.mp4" `
  --start-seconds 0 `
  --duration-seconds 20 `
  --render
```

Dependencias adicionales:

- `opencv-python`
- `ultralytics`

Si `ultralytics` no esta disponible, el script falla de forma explicita y no
afecta el resto del uploader.
Cuando el modelo se descarga por primera vez, queda cacheado en
`second_pass/outputs/yolo_reframe_experiments/models/`.

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
- `second_pass/queues/`: colas separadas de videos optimizados

Todos esos artefactos quedan fuera de Git.
