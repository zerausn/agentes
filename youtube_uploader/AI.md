# YouTube Uploader - AI Instructions

Este archivo complementa la guia global `Antigravity/AI.md` con reglas
especificas para este proyecto.

## Comandos de Ejecucion
- **Escaneo de videos:** `python video_scanner.py`
- **Clasificacion local:** `python classify_local_videos.py`
- **Limpieza de JSON:** `python clean_json.py`
- **Subida de videos:** `python uploader.py`
- **Programacion de borradores:** `python schedule_drafts.py`
- **Clipping local jornada 2:** `python second_pass/local_clip_optimizer.py`
- **Registro de optimizados:** `python second_pass/register_optimized_videos.py`

## Reglas de Desarrollo
- **Vanilla Python:** usar Python 3.10+ sin frameworks pesados.
- **Logging:** todo script operativo debe registrar salida local en `.log`.
- **Cuotas:** la rotacion de credenciales y `quota_status.json` son parte del
  flujo critico.
- **Rutas:** no hardcodear `C:\Users\...`; las bibliotecas locales se resuelven
  por `scanner.video_roots`, `YOUTUBE_UPLOADER_VIDEO_ROOTS` o el indice actual.

## Estado del Proyecto
- **Ruta de videos:** configurable y portable; el codigo ya no debe depender de
  una maquina concreta.
- **Limite de YouTube:** seguimos expuestos a `uploadLimitExceeded` cuando se
  acumulan demasiados borradores; `schedule_drafts.py` es la via operativa para
  moverlos al calendario.
- **Pipeline local:** `video_scanner.py` indexa, `classify_local_videos.py`
  completa metadatos y `uploader.py` rellena faltantes antes de subir.
- **Segunda jornada:** `second_pass/` genera clips derivados y los registra de
  forma explicita para no contaminar la subida cruda.
- **Progreso actual:** revisar `docs/PROGRESS.md`.
