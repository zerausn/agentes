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
  El runner `run_jornada1_normal.py` es el carril operativo normal para la
  jornada 1 de videos crudos: construye un calendario por dias, empareja las
  colas `reels/posts`, ejecuta las duplas FB+IG por asset y persiste el estado
  local en `meta_calendar.json`. Ahora tambien marca `in_progress`, escribe el
  calendario de forma atomica y puede reanudar desde el ultimo `meta_calendar`
  valido en lugar de resetear dias ya completados. `run_jornada1_supervisor.py`
  envuelve ese runner y lo relanza cuando termina de forma inesperada antes de
  completar la jornada. En paralelo, `meta_uploader.py` guarda checkpoints
  locales del upload resumible de Facebook (`upload_session_id` +
  `current_offset`) para intentar retomar el mismo transfer y no reiniciar
  siempre desde el byte cero.

## Carriles funcionales

- **Carril compartido Reel/Reel**: usa el subconjunto mas seguro para publicar
  el mismo asset en Facebook Reels e Instagram Reels.
- **Carril Facebook video estandar**: conserva un flujo separado para videos de
  pagina que no dependan del formato Reel. El transfer ahora reutiliza sesion
  HTTP por hilo y usa chunk adaptativo para reducir el overhead de miles de
  requests de `1 MB`.
- **Stories**: `Instagram Stories` se intenta solo cuando el asset vertical del
  dia cumple una politica conservadora (`<=60s`, vertical). `Facebook Stories`
  permanece fuera del alcance automatizado actual hasta versionar soporte
  oficial especifico para ese flujo.
- **Carril videos optimizados**: `second_pass/local_clip_optimizer.py` y
  `second_pass/prepare_second_jornada_meta.py` derivan clips `shared_reel` e
  `instagram_story` desde material crudo, escriben colas separadas en
  `second_pass/queues/` y solo promocionan derivados a `pendientes_reels.json`
  mediante opt-in explicito. Para full-length compatibles con IG existe
  `second_pass/transcode_instagram_api_safe.py`, que exporta una version
  completa H.264/AAC dentro del limite oficial y la deja en su propia cola de
  videos optimizados.
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
- **Supervision local**: `run_jornada1_supervisor.py` vigila la salida del
  runner normal. Si el proceso termina sin completar el calendario y sin dejar
  una pausa explicita por fallo, el supervisor espera unos segundos y reanuda
  la jornada desde `meta_calendar.json`.
- **Regla de 1 publicacion por dia real**: `run_jornada1_normal.py` puede
  planificar varios dias hacia adelante, pero la ejecucion viva ahora se corta
  al completar un solo dia real o cuando el siguiente `fecha` del calendario
  todavia es futuro. `run_jornada1_supervisor.py` tambien se detiene en ese
  punto y no relanza el runner hasta que corresponda el siguiente dia.
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
  cada fecha y pausar si falla la dupla principal de una publicacion.
- Si el runner termina sin cerrar el calendario, la siguiente ejecucion debe
  poder reanudar desde el mismo plan local y no duplicar dias ya completados.
- Un mismo archivo no debe republicarse si Meta ya devuelve evidencia remota
  de que el stem original existe en Facebook o Instagram.
- Aunque el calendario tenga varios dias planificados, la operacion viva debe
  respetar la regla de una publicacion por dia real.
