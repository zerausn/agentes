# Registro de Decisiones Tecnicas - YouTube Uploader

Este documento explica el por que de las decisiones clave tomadas en el
proyecto.

## 2026-04-07: Reparar `uploader.py` sobre la base sana de `HEAD`
- **Contexto:** el working tree quedo con `uploader.py` truncado y sin
  compilar.
- **Decision:** reconstruir el archivo completo y conservar la mejora util del
  watchdog de progreso dentro de una version consistente.
- **Motivo:** recuperar un entrypoint ejecutable sin perder el diagnostico de
  bloqueos de subida.

## 2026-04-08: No confundir `uploadLimitExceeded` con quota de credencial
- **Contexto:** el canal puede rechazar nuevas subidas o borradores aunque la
  credencial siga sana, y el uploader estaba rotando llaves igual que si fuera
  `quotaExceeded`.
- **Decision:** detener la jornada cuando aparezca `uploadLimitExceeded` y
  reservar la rotacion de credenciales solo para `quotaExceeded` o
  `rateLimitExceeded`.
- **Motivo:** no contaminar `quota_status.json` con falsos agotamientos y dejar
  claro que el siguiente paso operativo es programar o liberar borradores.

## 2026-04-08: Separar la prioridad de subida por carril
- **Contexto:** el uploader estaba ordenando toda la cola pendiente por peso
  global, mezclando `videos` y `shorts`.
- **Decision:** mantener dos colas separadas, una para `videos` y otra para
  `shorts`, ambas ordenadas por `size_mb` descendente.
- **Motivo:** conservar la regla de "mas pesados primero" dentro de cada tipo y
  al mismo tiempo respetar los huecos reales del calendario por carril.

## 2026-04-08: Elegir el siguiente carril por la fecha libre mas cercana
- **Contexto:** con colas separadas, el uploader necesita decidir cual carril
  atacar primero en cada iteracion.
- **Decision:** comparar la siguiente fecha libre de `video` y `short` usando el
  calendario local + YouTube; subir primero el carril con el hueco mas cercano.
  Si ambas fechas empatan, desempatar por el archivo mas pesado en cabeza de
  cola.
- **Motivo:** llenar antes el hueco operativo mas urgente sin perder la
  prioridad por peso dentro de cada carril.

## 2026-04-07: Raices de video configurables
- **Contexto:** varios scripts seguian amarrados a una ruta absoluta local.
- **Decision:** resolver las bibliotecas por `scanner.video_roots`,
  `YOUTUBE_UPLOADER_VIDEO_ROOTS` o inferencia desde el indice existente.
- **Motivo:** hacer el subproyecto portable entre maquinas y reorganizaciones de
  carpetas.

## 2026-04-07: Pipeline de metadatos auto-reparable
- **Contexto:** el flujo documentado no generaba siempre `type` ni
  `creation_date`, aunque el uploader los consumia.
- **Decision:** hacer que el scanner complete campos basicos, que
  `classify_local_videos.py` complete campos ricos y que `uploader.py` rellene
  faltantes antes de subir.
- **Motivo:** evitar titulos degradados, clasificaciones incompletas y
  dependencias frages del orden manual de ejecucion.

## 2026-04-07: Heuristica de borradores alineada con el prefijo `PW`
- **Contexto:** `schedule_drafts.py` seguia reconociendo solo el formato viejo
  "Performatic Writings".
- **Decision:** mover la heuristica de reconocimiento a `video_helpers.py` para
  aceptar formato actual, formato legacy y stems con timestamp.
- **Motivo:** impedir que borradores gestionados por el sistema queden marcados
  como privados intencionales.

## 2026-04-07: Segunda jornada separada para clipping local
- **Contexto:** se necesita mejorar videos localmente para una tanda posterior
  de publicacion, pero sin tocar la subida cruda ya operativa.
- **Decision:** crear `second_pass/` dentro de `youtube_uploader` y prohibir la
  incorporacion automatica de optimizados al indice principal.
- **Motivo:** evitar mezclar jornadas, permitir pruebas locales de clipping y
  mantener trazabilidad entre el material fuente y los derivados.

## 2026-04-07: Overrides de metadata por clip para la jornada 2
- **Contexto:** los clips optimizados necesitan un empaque distinto al titulo
  cronologico de la jornada 1.
- **Decision:** hacer que `video_helpers.py` y `uploader.py` acepten
  `title_override`, `description_override`, `tags_override` y overrides afines.
- **Motivo:** mejorar packaging y viralizacion sin alterar el comportamiento
  historico de los videos fuente.

## 2026-04-07: Scoring local orientado a retencion sin dependencias pesadas
- **Contexto:** el proyecto actual usa Python liviano y no debe depender de un
  stack ML obligatorio para funcionar.
- **Decision:** basar el primer clipping en `ffprobe` y `ffmpeg`, con bonus
  adicional si existe transcript sidecar.
- **Motivo:** obtener una segunda jornada util desde hoy, dejando Whisper, YOLO
  o detectores mas pesados como mejoras opcionales futuras.

## 2026-04-06: Mover `youtube_uploader` a la raiz del repo contenedor
- **Contexto:** el subproyecto habia quedado anidado por error dentro de
  `agentes/agentes/youtube_uploader`.
- **Decision:** ubicarlo en `youtube_uploader/` y reemplazar rutas historicas
  por rutas calculadas desde `__file__`.
- **Motivo:** evitar roturas al reorganizar el repo y alinear la estructura con
  la arquitectura declarada del workspace.

## 2026-04-06: Estrategia de doble via (double track)
- **Decision:** implementar calendarios paralelos para videos y shorts.
- **Motivo:** maximizar alcance y detectar huecos de programacion por tipo.

## 2026-04-06: Clasificacion de shorts (regla de 3 minutos)
- **Decision:** adoptar la politica nueva de YouTube para shorts verticales de
  hasta 3 minutos.
- **Motivo:** alinear la clasificacion local y la del canal con la politica
  vigente.

## 2026-04-06: Prefijo de titulos `PW`
- **Decision:** cambiar el prefijo de "Performatic Writings" a `PW`.
- **Motivo:** ganar brevedad y consistencia visual.
