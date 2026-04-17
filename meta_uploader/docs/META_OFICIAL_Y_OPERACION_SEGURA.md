# Meta Oficial y Operacion Segura

## Fuentes oficiales revisadas

- Instagram content publishing:
  [developers.facebook.com/docs/instagram-api/guides/content-publishing](https://developers.facebook.com/docs/instagram-api/guides/content-publishing)
- Instagram media reference:
  [developers.facebook.com/docs/instagram-platform/instagram-graph-api/reference/ig-user/media](https://developers.facebook.com/docs/instagram-platform/instagram-graph-api/reference/ig-user/media)
- Instagram media publish reference:
  [developers.facebook.com/docs/instagram-platform/instagram-graph-api/reference/ig-user/media_publish](https://developers.facebook.com/docs/instagram-platform/instagram-graph-api/reference/ig-user/media_publish)
- Facebook video publishing:
  [developers.facebook.com/docs/video-api/guides/publishing](https://developers.facebook.com/docs/video-api/guides/publishing)
- Facebook Reels publishing:
  [developers.facebook.com/docs/video-api/guides/reels-publishing](https://developers.facebook.com/docs/video-api/guides/reels-publishing)
- Sample repo oficial de Meta:
  [github.com/fbsamples/reels_publishing_apis](https://github.com/fbsamples/reels_publishing_apis)

## Hallazgos clave

### Instagram

- Meta documenta un flujo de tres pasos: crear contenedor, subir video y luego
  publicar el contenedor.
- `media_publish` trabaja con `creation_id`; el estado del video se consulta con
  `GET /{ig-container-id}?fields=status_code`.
- La documentacion oficial que revisamos no es totalmente consistente sobre el
  limite numerico; por eso el codigo debe consultar
  `GET /{ig-user-id}/content_publishing_limit` antes de publicar y no fiarse de
  un numero hardcodeado.
- Para Reels, Meta documenta `caption`, `cover_url`, `thumb_offset`,
  `share_to_feed`, `audio_name` y `upload_type=resumable` en la creacion del
  contenedor.
- Meta exige token de usuario para endpoints de publicacion de Instagram en la
  referencia oficial.

### Facebook

- Facebook Reels tiene un limite documentado de 30 publicaciones API por un
  periodo movil de 24 horas.
- El flujo de Reels es asincrono: `start`, upload binario y `finish`, seguido
  de verificacion de estado.
- Meta documenta especificaciones tecnicas claras para Reels de Facebook:
  `.mp4`, 9:16, minimo 540x960, recomendado 1080x1920, 24-60 fps y 3-90
  segundos.
- El flujo general de videos de pagina tambien admite subidas grandes y
  mecanismos de upload resumible.

## Recomendaciones para no arriesgar cuenta o app

- Usa solo endpoints oficiales; no automatices likes, follows, mensajes ni
  acciones de engagement no documentadas.
- Implementa backoff y corte limpio ante errores 4xx repetidos.
- No declares exito antes de que el asset termine `processing` o `publishing`.
- Evita reintentos ciegos de un mismo video cuando Meta devuelve errores de
  validacion tecnica.
- Mantiene PPA y 2FA al dia en la pagina conectada; Meta documenta que, si
  faltan, la solicitud puede fallar.
- No subas duplicados masivos ni fuerces varias publicaciones por minuto si la
  cuenta no tiene historial estable.
- Conserva logs tecnicos, pero no tokens.

## Politica local recomendada

- Para el carril compartido FB Reel + IG Reel: 3-90 segundos y vertical.
- Para Instagram-only en el futuro: abrir un carril separado para videos que
  superen 90 segundos pero sigan dentro de los limites oficiales de IG.
