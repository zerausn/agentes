# Meta Uploader AI Instructions

Este directorio contiene el orquestador asíncrono para subir Reels y Posts a Instagram y Facebook mediante la Graph API v19.0.

## Reglas de Desarrollo Locales
- Respetar los límites de Meta: 100 IG Reels/día, 30 FB Reels/día.
- `classify_meta_videos.py` debe evaluar videos locales como 9:16 y 5-90s obligatoriamente con ffprobe.
- Actualizar `docs/PROGRESS.md` antes de terminar iteraciones importantes.
- No guardar tokens en texto plano, usar entorno.

## Archivos y Endpoints Claves
- IG Container Post: `/{ig-user-id}/media`
- IG Container Publish: `/{ig-user-id}/media_publish`
- FB Reel Start: `POST graph.facebook.com/v19.0/{page-id}/video_reels`
- FB Reel Upload: `POST rupload.facebook.com/video-upload/v19.0/{video-id}`
- FB Reel Publish: `POST graph.facebook.com/v19.0/{page-id}/video_reels (upload_phase=finish)`
