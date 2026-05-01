# Estado del Progreso - YouTube Uploader

Estado actual del proyecto al **15 de Abril de 2026**.

## Infraestructura del subproyecto
- [x] `youtube_uploader/` vive en la raiz del repo `agentes`.
- [x] `uploader.py` vuelve a compilar y conserva watchdog de progreso.
- [x] Las rutas absolutas se eliminaron del codigo operativo del subproyecto.
- [x] Existe una capa compartida `video_helpers.py` para config, metadatos y
  heuristicas comunes.

## Pipeline local
- [x] `video_scanner.py` indexa y completa `creation_date`.
- [x] `classify_local_videos.py` completa `type`, `duration` y `dimensions`.
- [x] `check_channel_videos.py` mueve duplicados al folder de exclusiones sin
  depender de una ruta fija.
- [x] `uploader.py` rellena faltantes antes de subir para tolerar indices
  parciales.
- [x] `uploader.py` acepta overrides de metadata para clips de segunda jornada.
- [x] `uploader.py` ya separa la prioridad de `videos` y `shorts` en colas
  independientes por peso.
- [x] `uploader.py` selecciona el siguiente carril comparando el primer hueco de
  calendario disponible para `video` y `short`.
- [x] `uploader.py` ya no comparte el mismo cliente HTTP entre la subida
  resumible y la verificacion post-upload.
- [x] Implementar logica de clasificacion 3-min Shorts para carril compartido.
- [x] Integrar `manage_playlist.py` en el loop principal de `uploader.py`.
- [x] Crear Agente de Teasers (`teaser_uploader.py`) independiente para reciclaje de IG.
- [x] Implementar monitoreo paralelo de procesamiento HD (anti-zombie).
- [x] `video_scanner.py` y las colas de `uploader.py` ignoran artefactos
  `*.faststart.tmp.*`.

## Segunda jornada local
- [x] Existe `second_pass/local_clip_optimizer.py` para analizar y renderizar
  clips derivados.
- [x] Existe `second_pass/register_optimized_videos.py` para incorporar
  optimizados al indice solo bajo accion explicita.
- [x] Los artefactos de `second_pass/` quedan fuera de Git.
- [x] Hay pruebas unitarias para helpers de metadata y registro de optimizados.

## Validacion reciente
- [x] `python -m compileall .`
- [x] `python -m unittest discover -s tests -v`
- [x] Se verifico que el codigo operativo ya no contiene referencias activas a
  rutas absolutas de una maquina concreta.
- [x] `uploader.py` ya no marca falsamente una credencial como agotada cuando
  el error real es `uploadLimitExceeded` del canal.
- [x] `python rescue_stuck_processing.py` se ejecuto contra el canal y genero
  `processing_rescue_report.json`.

## Riesgos operativos que siguen vigentes
- **Cuota de API:** el cambio no elimina los resets diarios de quota.
- **Limite del canal:** `uploadLimitExceeded` sigue dependiendo del estado del
  canal y de la programacion de borradores.
- **Dependencia externa:** la clasificacion rica requiere `ffprobe` disponible
  en el sistema para completar `type`, `duration` y `dimensions`.
- **Second pass:** el scoring mejora mucho si el video fuente tiene `.srt`,
  `.vtt` o transcript `.json` al lado del master.
- **Procesamiento huérfano:** aun quedan 3 videos sin copia procesada en el
  canal y dependen de que el nudge reforzado o YouTube Studio los destrabe.

- [x] `python cleanup_zombies.py` ejecutado en dos fases, eliminando un total de **34 videos duplicados** que ya tenian copia buena.
- [x] Refuerzo de `nudge_stuck_videos.py` con modo `heavy` para forzar re-procesamiento.
- [x] Aplicacion de Heavy Nudge a **4 videos huerfanos** restantes.
- [x] Verificacion final: el conteo de videos atascados bajo de +40 a solo 4.

### 2026-04-14: Correccion de videos atascados (YouTube)
- [x] Diagnostico mediante script implementado para detectar videos con
  `uploadStatus: uploaded` en lugar de `processed`.
- [x] Ejecucion de `nudge_stuck_videos.py` para forzar revision y procesamiento
  de videos estancados en los que ya no existia copia local.
- [x] Adicion de polling post-upload (`wait_for_processing`) durante 10 minutos
  para confirmar si YouTube realmente proceso el archivo.
- [x] Adicion de `notifySubscribers=False` para evitar spam en uploads masivos.

### 2026-04-15: Rescate y limpieza masiva de duplicados
- [x] `video_helpers.py` ya normaliza stems con sufijo `.faststart.tmp`,
  evitando titulos contaminados como `(archivo.faststart.tmp)`.
- [x] Existe `rescue_stuck_processing.py`, que reconcilia videos `uploaded`
  contra copias hermanas `processed` por stem canonico y repara metadata de la
  copia buena sin borrar nada del canal.
- [x] Limpieza de "Wave 1": Borrado de **28 zombis** confirmados (duplicados con copia OK).
- [x] Limpieza de "Wave 2": Borrado de **6 zombis** adicionales detectados tras la primera limpieza.
- [x] Aplicacion de **Heavy Nudge** a los huérfanos restantes (4 videos): `qLwX8PFeI_k`, `YsR_AG9A86I`, `eDJGjzbQjAo`, `Z-LEw-ti4OA`.
- [x] `diagnose_processing.py` actualizado para reportar el estado final limpio.
### 2026-04-17: Automatización de Playlist y SEO
- [x] Creación de `manage_playlist.py` con rotación de 4 llaves de API.
- [x] Integración de sincronización diaria automática en `EJECUTAR_SUBIDA.bat`.
- [x] Estandarización de títulos a formato limpio: `#PW | (nombre_del_video)`.
- [x] Estandarización de descripción a texto único de redes sociales (clínico).
- [x] Inclusión de etiqueta obligatoria `performatic writings`.
- [x] Solución al problema de visibilidad de playlist (fuerza estado Público).
