# Meta Uploader - AI Instructions

Este contexto aplica solo a `meta_uploader/`.

## Objetivo

Automatizar publicaciones hacia Facebook e Instagram usando las APIs oficiales
de Meta, sin mezclar esta logica con `youtube_uploader`.

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
- La segunda jornada puede derivar `shared_reel` e `instagram_story` desde
  `pendientes_posts.json` usando `second_pass/prepare_second_jornada_meta.py`.
  Solo debe fusionar esos derivados dentro de `pendientes_reels.json` cuando se
  pida de forma explicita; por defecto las colas optimizadas viven separadas.
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
