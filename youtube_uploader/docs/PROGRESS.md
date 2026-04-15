# Estado del Progreso - YouTube Uploader

Estado actual del proyecto al **07 de Abril de 2026**.

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

## Riesgos operativos que siguen vigentes
- **Cuota de API:** el cambio no elimina los resets diarios de quota.
- **Limite del canal:** `uploadLimitExceeded` sigue dependiendo del estado del
  canal y de la programacion de borradores.
- **Dependencia externa:** la clasificacion rica requiere `ffprobe` disponible
  en el sistema para completar `type`, `duration` y `dimensions`.
- **Second pass:** el scoring mejora mucho si el video fuente tiene `.srt`,
  `.vtt` o transcript `.json` al lado del master.

### 2026-04-14: Corrección de videos atascados (YouTube)
- [x] Diagnóstico mediante script implementado para detectar videos con uploadStatus: uploaded en lugar de processed.
- [x] Ejecución de script de 
udge (metadata touch por API) para forzar revisión y procesamiento de 30 videos estancados en los que ya no existía copia local.
- [x] Adición de polling post-upload (wait_for_processing) durante 10 minutos para confirmar si Youtube realmente procesó el archivo.
- [x] Adición de flag 
otifySubscribers=False (evitar spam en uploads masivos).
