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

## Documentacion publica para App Review

- [`docs/PRIVACY_POLICY.md`](./docs/PRIVACY_POLICY.md)
- [`docs/DATA_DELETION.md`](./docs/DATA_DELETION.md)
- [`docs/TERMS_OF_SERVICE.md`](./docs/TERMS_OF_SERVICE.md)
- [`docs/APP_REVIEW_SITE.md`](./docs/APP_REVIEW_SITE.md)
- Sitio estatico listo para GitHub Pages en `site/`
