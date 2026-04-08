# YOLO Reframer Experimental

Esta herramienta existe para probar el enfoque de `performatic_engine` sin
meterlo todavia en el flujo real de `meta_uploader`.

Archivo principal:

- `second_pass/experimental_yolo_reframer.py`

## Objetivo

Probar si un reencuadre 9:16 guiado por YOLO mejora clips verticales antes de
integrarlo al clipping de segunda jornada o al runner principal.

## Lo que SI hace

- analiza un segmento puntual de video
- usa YOLOv8 para detectar personas
- calcula un plan de crop vertical con suavizado
- guarda un manifest JSON del movimiento de crop
- opcionalmente renderiza un clip experimental aparte

## Lo que NO hace

- no modifica `pendientes_posts.json`
- no modifica `pendientes_reels.json`
- no entra a `run_jornada1_normal.py`
- no cambia `prepare_second_jornada_meta.py`
- no publica nada a Meta

## Salidas

Todo queda separado en:

- `second_pass/outputs/yolo_reframe_experiments/plans/`
- `second_pass/outputs/yolo_reframe_experiments/renders/`

## Uso

Plan solamente:

```powershell
python second_pass/experimental_yolo_reframer.py `
  --input "C:\ruta\video.mp4" `
  --start-seconds 5 `
  --duration-seconds 20
```

Plan + render:

```powershell
python second_pass/experimental_yolo_reframer.py `
  --input "C:\ruta\video.mp4" `
  --start-seconds 5 `
  --duration-seconds 20 `
  --render
```

## Dependencias

- `opencv-python`
- `ultralytics`

## Estado

Herramienta experimental.

La intencion es comparar resultados primero. Solo si el comportamiento resulta
bueno se deberia estudiar una integracion con la segunda jornada.
