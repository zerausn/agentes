# Meta Uploader Agent (Facebook & Instagram)

Este subproyecto automatiza publicaciones de video hacia Facebook e Instagram
usando APIs oficiales de Meta.

## Estado

En desarrollo activo. Ya existen scripts de clasificacion, diagnostico, subida
resumible y utilidades de operacion, pero el flujo todavia se esta endureciendo
contra la documentacion oficial.

## Setup rapido

```powershell
python -m pip install -r requirements.txt
Copy-Item .env.example .env
# Edita .env con tus credenciales reales
python get_meta_ids.py
python classify_meta_videos.py "C:\ruta\a\videos"
python meta_calendar_generator.py
```

## Requisitos locales

- Python 3.10+
- `ffmpeg` y `ffprobe` disponibles en PATH
- Credenciales de Meta en `.env`

## Variables importantes

- `META_IG_USER_TOKEN` o `META_PAGE_TOKEN` para Instagram
- `META_FB_PAGE_TOKEN` para endpoints de pagina de Facebook
- `META_FB_PAGE_ID`
- `META_IG_USER_ID`
- `META_APP_ID` para flujos avanzados de uploads
- `META_GRAPH_API_VERSION` para fijar la version del Graph API
- `META_ENABLE_UPLOAD=1` solo cuando quieras habilitar los scripts manuales que publican de verdad
- `META_UPLOAD_STALL_CHECK_SECONDS` para ajustar cada cuanto se vigila una subida
- `META_UPLOAD_STALL_MAX_NO_PROGRESS_CHECKS` para definir cuantas verificaciones sin avance disparan alerta
- `META_FB_UPLOAD_CHUNK_BYTES` para ajustar el tamano objetivo del chunk de Facebook (default actual: `8 MB`)
- `META_FB_UPLOAD_MIN_CHUNK_BYTES` como piso de seguridad si el uploader detecta fallos transitorios y necesita bajar el chunk automaticamente

## Regla de Git

No se deben subir a Git los tokens, logs, inventarios exportados, colas
generadas ni videos transcodificados.

## Utilidades incluidas

- `check_page_v2.py`: valida acceso basico a la pagina y al edge `/videos`
- `debug_token.py`: imprime el diagnostico del token actual
- `get_page_token.py`: intenta derivar `META_FB_PAGE_TOKEN` a partir de `META_PAGE_TOKEN`
- `diag_sizes.py`: lista los videos mas pesados de una carpeta
- `transcode_batch.py`: prepara una cola de videos optimizados para IG
- `test_batch_upload.py` y `test_batch_upload_v2.py`: scripts manuales con opt-in explicito
- `test_single_scheduled.py`: sonda manual de un solo asset pesado para probar formatos activos y dejar evidencia estructurada local
- `run_jornada1_normal.py`: runner operativo de jornada 1 para videos crudos. Genera `meta_calendar.json` por dias, prioriza lo mas pesado primero dentro de cada fecha, ejecuta `FB Reel + IG Reel` en el carril compartido, `FB Post + IG Feed` para el resto, intenta `IG Story` solo cuando el asset vertical pasa una politica conservadora y deja `Facebook Stories` como salto explicito por soporte no versionado.
- `second_pass/prepare_second_jornada_meta.py`: prepara derivados de segunda jornada desde colas crudas, acumula colas `reel/story` optimizadas y puede promocionar esos reels a `pendientes_reels.json` solo con opt-in explicito.
- `second_pass/experimental_yolo_reframer.py`: herramienta aparte para probar reencuadre inteligente 9:16 con YOLO antes de integrarlo al clipping real.

## Jornada 1

Uso sugerido del runner normal:

```powershell
$env:META_ENABLE_UPLOAD = "1"
python run_jornada1_normal.py --days 7 --post-start-index 0 --reel-start-index 0
```

Notas:

- Usa siempre videos crudos; no toca originales ni depende de `second_pass/`.
- Se apoya en `pendientes_reels.json` y `pendientes_posts.json`, que ya vienen priorizados por peso.
- Escribe `meta_calendar.json` como calendario operativo local, fuera de Git.
- Si falla la dupla principal de un asset (`FB+IG`), pausa la jornada para no quemar cola.
- `IG Story` se trata como carril best-effort sobre el reel vertical del dia.
- `Facebook Stories` sigue fuera del flujo automatizado actual.
- El carril `Facebook Post` ahora arranca con chunk mayor y reduce temporalmente el chunk si detecta fallos transitorios.
- El logging operativo se separa en tres archivos locales: `meta_uploader.log` (maestro), `meta_uploader_facebook.log` y `meta_uploader_instagram.log`.

## Documentacion publica para App Review

- [`docs/PRIVACY_POLICY.md`](./docs/PRIVACY_POLICY.md)
- [`docs/DATA_DELETION.md`](./docs/DATA_DELETION.md)
- [`docs/TERMS_OF_SERVICE.md`](./docs/TERMS_OF_SERVICE.md)
- [`docs/APP_REVIEW_SITE.md`](./docs/APP_REVIEW_SITE.md)
- Sitio estatico listo para GitHub Pages en `site/`
