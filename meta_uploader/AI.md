# Meta Uploader - AI Instructions

Este contexto aplica solo a `meta_uploader/`.

## Objetivo

Automatizar publicaciones hacia Facebook e Instagram usando las APIs oficiales
de Meta, sin mezclar esta logica con `youtube_uploader`.

## Convencion operativa

- Si el usuario dice `sube videos a Meta`, interpreta eso como el flujo
  programado actual de Meta, no como una invocacion directa a `meta_uploader.py`.
- El entrypoint humano recomendado es `schedule_jornada1_supervisor.py`.
- El nombre operativo nuevo es `videos optimizados`, aunque `second_pass/`
  pueda seguir existiendo internamente.

## Reglas operativas

- Usa solo endpoints documentados por Meta.
- Para Instagram, trata `content_publishing_limit` como fuente de verdad del
  limite efectivo antes de publicar.
- La clasificacion `3-90s` y vertical se usa como politica conservadora para el
  subconjunto compartido FB Reel + IG Reel; no reemplaza las especificaciones
  completas de Meta.
- El runner operativo de jornada 1 usa videos crudos y separa los carriles asi:
  reel-safe -> `FB Reel + IG Reel`; no reel-safe -> `FB Post + IG Feed`;
  `IG Story` solo como intento best-effort cuando el asset vertical pasa una
  politica conservadora; `Facebook Stories` sigue fuera del flujo automatizado.
- Los `videos optimizados` pueden derivar `shared_reel` e `instagram_story`
  desde `pendientes_posts.json` usando `second_pass/prepare_second_jornada_meta.py`.
  Solo debe fusionar esos derivados dentro de `pendientes_reels.json` cuando se
  pida de forma explicita; por defecto las colas optimizadas viven separadas.
- El uploader de Facebook usa sesion HTTP persistente por hilo y chunk adaptativo:
  arranca con `META_FB_UPLOAD_CHUNK_BYTES` y puede bajar hasta
  `META_FB_UPLOAD_MIN_CHUNK_BYTES` si la sesion se vuelve inestable.
- Cualquier experimento de reencuadre YOLO debe quedarse primero como
  herramienta aislada (`second_pass/experimental_yolo_reframer.py`) y no entrar
  al flujo productivo hasta que las pruebas manuales demuestren valor real.
- No subas `.env`, tokens, inventarios exportados, colas generadas, videos
  optimizados ni logs.
- Actualiza `docs/PROGRESS.md` y `docs/DECISIONS.md` cuando cambie el flujo.

## Endpoints clave

- `POST /{ig-user-id}/media`
- `POST /{ig-user-id}/media_publish`
- `GET /{ig-container-id}?fields=status_code`
- `GET /{ig-user-id}/content_publishing_limit`
- `POST /{page-id}/video_reels`
- `POST /{page-id}/videos`
