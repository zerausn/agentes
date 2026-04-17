# Segunda Jornada - Investigacion Aplicada

## Objetivo

Convertir un video fuente ya listo para subida cruda en clips derivados con mas
capacidad de retencion, sin tocar el carril base de `uploader.py`.

## Que se implemento

- normalizacion opcional VFR -> CFR
- deteccion de cambios de escena
- deteccion de silencios
- deteccion de negro y fades
- lectura de transcript sidecar (`.srt`, `.vtt`, `.json`)
- scoring de ventanas con enfasis en hook temprano
- render de verticales y teaser cuadrado
- registro explicito al indice con overrides de metadata

## Logica de viralizacion aplicada

- **Hook temprano:** si el transcript arranca con pregunta, negacion,
  advertencia o frase de curiosidad, el clip sube de score.
- **Retencion visual:** si una ventana mantiene cambios de escena y evita
  tramos muertos, recibe prioridad.
- **Retencion auditiva:** si el arranque tiene voz y no silencio, suma puntos.
- **Packaging separado:** los derivados pueden llevar `title_override`,
  `description_override` y `tags_override`.

## Fuentes tecnicas de referencia

- YouTube Data API upload guide:
  https://developers.google.com/youtube/v3/guides/uploading_a_video
- Politica vigente de Shorts de hasta 3 minutos:
  https://support.google.com/youtube/answer/15424877
- FFmpeg filters:
  https://ffmpeg.org/ffmpeg-filters.html
- PySceneDetect:
  https://www.scenedetect.com/docs/latest/
- Whisper timestamped:
  https://github.com/linto-ai/whisper-timestamped
- TransNetV2:
  https://github.com/soCzech/TransNetV2
- Ultralytics YOLO:
  https://github.com/ultralytics/ultralytics

## Lo que queda como mejora futura

- transcripcion local automatica con Whisper cuando el entorno la tenga
- reencuadre dinamico con YOLO en vez de crop fijo
- ranking semantico asistido por LLM sobre manifests ya generados
