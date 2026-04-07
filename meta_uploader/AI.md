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
