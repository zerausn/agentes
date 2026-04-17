# Arquitectura - Meta Uploader

## Proposito

Subir contenido de video a Facebook e Instagram usando Graph API y Video API,
con una capa de automatizacion separada del repo contenedor.

## Componentes

- `meta_uploader.py`: cliente principal de autenticacion, limites, subida y
  polling, ahora con watchdog de estancamiento, diagnostico basico de
  conectividad y una primera capa de retries clasificados para requests JSON y
  uploads binarios.
- `classify_meta_videos.py`: clasifica videos locales para el carril compartido
  Reel/Reel con reglas conservadoras.
- `meta_calendar_generator.py`: construye una cola local de publicacion.
- Scripts de diagnostico: `get_meta_ids.py`, `get_page_token.py`,
  `debug_token.py`, `check_page_v2.py`, `diag_sizes.py`.
- Scripts de operacion: `transcode_batch.py`, `test_batch_upload.py`,
  `test_batch_upload_v2.py`, `test_single_scheduled.py`,
  `run_jornada1_normal.py`, `run_jornada1_supervisor.py`.
  El runner `test_batch_upload.py` ya puede reintentar un asset transitorio y
  pausar el batch para no consumir la cola a ciegas.
- `reconcile_meta_cloud.py`: Motor de reconciliación rápida (Reconciliación 3.0). Realiza una limpieza triple nuclear basada en una caché masiva de 2000 videos remotos. Sincroniza el sistema purgando las colas `pendientes_*.json` y marcando el calendario como `completed`.
- `run_jornada1_normal.py`: El runner operativo normal para la jornada 1. Ahora **enfocado exclusivamente en Facebook**, delegando Instagram al Vigía para maximizar la resiliencia de la ráfaga. Implementa el auto-move de archivos completados.
- `fb_to_ig_vigia.py`: Agente Vigía encargado de la reconciliación FB -> IG. Rescata los videos `#full` de Facebook y los publica en Instagram (Feed/Reel/Stories), permitiendo que el runner principal se libre de la carga de Instagram.

- **Delegación Total de Instagram**: Instagram ya no se procesa en el runner principal. El runner marca las tareas como `delegated_to_vigia`. Esto elimina los fallos de IG como causa de aborto de la ráfaga de Facebook y ahorra tiempo de CPU al no transcodificar para IG en el flujo principal.
- **Carril Facebook Dual (Teaser + Full)**: Facebook sigue recibiendo dos versiones: un `#teaser` (Reel inmediato de 60s) y el video completo (`#full`) programado. Esto maximiza el alcance orgánico inmediato mientras se construye la biblioteca completa.
- **Vigía (Rescate FB -> IG)**: El Vigía monitorea Facebook, detecta los videos `#full` y los promueve a Instagram. Los `#teaser` de Facebook son ignorados por el Vigía para mantener el feed de Instagram limpio de fragmentos cortos duplicados.
- **Gestión de Archivos Post-Subida**: Una vez completada una jornada, el sistema mueve automáticamente los archivos:
    - Videos originales -> `ya_subidos_fb_ig/`
    - Archivos temporales (`slice_60s`, `ig_compat`) -> `ya_subidos_ig_temp/`
    - Ambas carpetas son excluidas de futuros escaneos para evitar duplicados.
- **Preflight IG en jornada 1**: antes de intentar `instagram_feed` o
  `instagram_reel`, el runner valida el asset crudo contra limites oficiales
  del flujo `REELS`/`share_to_feed` y `STORIES` (tamano, ancho, fps, bitrate,
  duracion, codec). Si el crudo no cumple, IG se marca como salto operativo
  hacia videos optimizados en vez de disparar un upload condenado a fallar.
- **Persistencia y reanudacion de jornada 1**: el calendario local registra
  estados `pending`, `in_progress`, `published`, `published_with_ig_skip` y
  `paused_on_failure`. Si el proceso cae sin cerrar el dia, un reinicio del
  runner convierte el `in_progress` previo en reintento del mismo asset y
  conserva los dias ya completados.
- **Guardia remota anti-duplicados**: antes de subir un asset, el runner
  consulta los ultimos videos de Facebook y los ultimos medios de Instagram
  buscando el stem original del archivo en caption/descripcion. Si ya existe
  un match remoto, registra `already_exists_remote` y evita una nueva
  publicacion aunque el calendario local haya quedado desfasado por una caida.
- **Programados visibles de verdad**: la deteccion remota de Facebook ya no se
  limita a `/{page}/videos`; tambien consulta `/{page}/scheduled_posts`, porque
  parte de los videos futuros vive solo ahi con el stem en `message`. Ese mismo
  barrido alimenta la limpieza previa de `pendientes_posts.json` y
  `pendientes_reels.json` antes de reconstruir `meta_calendar.json`.
- **Supervision local**: `run_jornada1_supervisor.py` vigila la salida del
  runner normal. Si el proceso termina sin completar el calendario y sin dejar
  una pausa explicita por fallo, el supervisor espera unos segundos y reanuda
  la jornada desde `meta_calendar.json`.
- **Regla de 1 publicacion por dia real**: `run_jornada1_normal.py` puede
  planificar varios dias hacia adelante, pero la ejecucion viva ahora se corta
  al completar un solo dia real o cuando el siguiente `fecha` del calendario
  todavia es futuro. `run_jornada1_supervisor.py` tambien se detiene en ese
  punto y no relanza el runner hasta que corresponda el siguiente dia.
- **Reel inmediato como best-effort en carril post**: para el carril
  `Facebook Post + IG Feed`, el objetivo primario es que el video completo
  quede programado. Si ese programado ya existe o se confirma remoto, un fallo
  del reel inmediato auxiliar no debe devolver el asset a estado pendiente ni
  disparar reintentos duplicados del video completo.
- **Entrypoint humano recomendado**: cuando el operador diga "sube videos a
  Meta", debe arrancarse `run_jornada1_supervisor.py` para la jornada de
  publicacion programada.
- **Carril experimental YOLO**: `second_pass/experimental_yolo_reframer.py`
  existe como laboratorio aparte para comparar recorte centrado vs reencuadre
  guiado por deteccion de personas. Sus planes y renders viven bajo
  `second_pass/outputs/yolo_reframe_experiments/` y no tocan colas ni uploads.
- **Artefactos locales**: colas JSON, inventarios y videos optimizados se
  generan localmente y quedan fuera de Git.
- **Observabilidad local**: el uploader deja un log maestro
  (`meta_uploader.log`) y dos logs derivados por plataforma
  (`meta_uploader_facebook.log`, `meta_uploader_instagram.log`) para separar
  mejor las trazas de transfer/polling de Facebook de los eventos de
  contenedores/publicacion en Instagram.

## Reglas

- La configuracion sensible vive en variables de entorno.
- El subproyecto debe poder moverse dentro del repo sin romper rutas locales.
- El codigo no debe asumir exito inmediato despues de `finish`; Meta procesa
  videos de forma asincrona y requiere polling.
- Las subidas largas deben alertar si se estancan y registrar si el problema
  parece de conectividad local o de la sesion contra Meta.
- Los runners no deben avanzar automaticamente al siguiente asset cuando el
  ultimo fallo parezca transitorio o de red.
- La jornada 1 debe priorizar primero el asset mas pesado disponible dentro de
  cada fecha y procesar un dia real a la vez en modo secuencial para mitigar
  bloqueos por spam.
- Un mismo archivo no debe republicarse si Meta ya devuelve evidencia remota
  de que el stem original existe en Facebook o Instagram.
- La Limpieza Triple Nuclear asegura la coherencia absoluta entre el disco, las colas JSON y el calendario.
- Todo cambio estructural debe reflejarse en ARCHITECTURE.md, DECISIONS.md, PROGRESS.md y HISTORIAL_CONVERSACIONES.md.
