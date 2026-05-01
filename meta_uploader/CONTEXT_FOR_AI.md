# Meta Uploader - Context for AI

Lee este archivo ANTES de hacer cualquier cambio en `meta_uploader/`.

## ¿Qué se busca?

Automatizar la publicación de ~220 videos de arte performático en Facebook e Instagram, programando 1 video por día dentro de una ventana móvil de 28 días. El sistema debe ser autónomo, resiliente a fallos de red y capaz de detectar duplicados.

## ¿Qué se necesita?

1. **Subida Resiliente**: Archivos de 1-3 GB deben subirse con chunks adaptivos y checkpoints resumibles.
2. **Detección de Duplicados**: Cruzar el filesystem local con la nube de Meta para evitar resubidas.
3. **Modo Anti-Spam**: Procesar un día a la vez (modo secuencial) para evitar bloqueos de Meta.
4. **Programación Futura**: Usar la API de Meta para programar videos hasta 28 días en el futuro.
5. **Crossposting**: Publicar el mismo video en Facebook (como Post y Reel) e Instagram (como Feed y Reel).

## Fallas No Corregidas

| Falla | Severidad | Descripción |
|-------|-----------|-------------|
| Error 368 (Rate Limit) | ALTA | Meta bloquea temporalmente cuando detecta ráfagas. Mitigado con modo secuencial pero puede reaparecer. |
| ConnectionResetError(10054) | MEDIA | Videos pesados (+2 GB) pueden estancarse durante `rupload`. El watchdog detecta pero no siempre recupera. |
| Instagram Codec Rejection | MEDIA | Videos crudos con bitrate/fps alto son rechazados por IG. Requieren transcoding en `second_pass/`. |
| IG Story ProcessingFailedError | BAJA | Clips verticales derivados fallan en `rupload` de Stories. Sin diagnóstico claro aún. |
| Tesseract `spa` missing | BAJA | Algunos entornos no tienen el diccionario español instalado. |

## Arquitectura del Código

```
meta_uploader/
├── meta_uploader.py           → Cliente HTTP: auth, subida resumible, polling, caché masiva
├── run_jornada1_normal.py     → Runner diario: calendario, modo secuencial, ejecución FB+IG
├── run_jornada1_supervisor.py → Supervisor: relanza runners caídos
├── schedule_jornada1_meta.py  → Construye el plan de 28 días con franjas horarias
├── schedule_jornada1_supervisor.py → Supervisor del schedulador
├── reconcile_meta_cloud.py    → Limpieza Triple Nuclear (disco + JSON + calendario)
├── classify_meta_videos.py    → Clasifica videos para carril Reel vs Post
├── meta_calendar_generator.py → Genera meta_calendar.json
├── fb_to_ig_vigia.py          → Vigía de crossposting FB→IG
├── docs/                      → ARCHITECTURE, DECISIONS, PROGRESS, HISTORIAL
├── second_pass/               → Videos optimizados y experimentos YOLO
└── site/                      → Sitio estático para App Review de Meta
```

## Flujo de Ejecución (Jornada 1)

1. `schedule_jornada1_supervisor.py` arranca todo.
2. `reconcile_meta_cloud.py` hace barrido masivo de 2000 videos remotos (Limpieza Triple).
3. `classify_meta_videos.py` clasifica los videos locales en reels vs posts.
4. `schedule_jornada1_meta.py` construye `meta_calendar.json` (28 días).
5. `run_jornada1_normal.py` ejecuta día por día en modo secuencial:
   - Para cada día: sube Post a FB, luego Reel a FB, luego Feed a IG.
   - Mueve archivo a `ya_subidos_fb_ig/` al terminar.
6. Si el runner cae, el supervisor lo relanza desde `meta_calendar.json`.

## Variables de Entorno Clave

- `META_ENABLE_UPLOAD=1`: Habilita subidas reales (0 = dry run).
- `META_PAGE_ACCESS_TOKEN`: Token de la página de Facebook.
- `META_PAGE_ID`: ID de la página de Facebook.
- `META_IG_USER_ID`: ID del usuario de Instagram.
- `META_FB_UPLOAD_CHUNK_BYTES`: Tamaño de chunk para subida (default 16MB).

## Decisiones Críticas (Resumen)

- **D29**: Limpieza Triple Nuclear: sincronización atómica de disco + JSON + calendario.
- **D30**: Modo secuencial de días para mitigar Error 368.
- **D27**: `scheduled_posts` como fuente obligatoria de verdad para programados.
- **D25**: Guardia remota anti-duplicados antes de cada subida.

Para el registro completo, lee `docs/DECISIONS.md`.
