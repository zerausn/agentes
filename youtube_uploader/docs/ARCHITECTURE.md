# Arquitectura del Sistema - YouTube Uploader

Este documento describe el diseno tecnico del automatizador de videos para el
canal "Performatic Writings".

## Ubicacion del subproyecto
- Este subproyecto vive en `youtube_uploader/` dentro de la raiz del repo
  contenedor `agentes`.
- Los scripts resuelven su directorio base desde `__file__`.

## Componentes principales
1. **Scanner (`video_scanner.py`)**
   Indexa una o varias bibliotecas locales, filtra extensiones y tamano y
   completa campos basicos como `filename` y `creation_date`.
2. **Clasificador (`classify_local_videos.py`)**
   Usa `ffprobe` para completar `type`, `duration` y `dimensions` en el indice
   local.
3. **Uploader (`uploader.py`)**
   Motor de subida fraccionada con reintentos, rotacion de credenciales,
   watchdog de progreso y mecanismo de parada mediante `STOP`.
4. **Scheduler (`schedule_drafts.py`)**
   Programa borradores del canal y distingue entre borradores gestionados por el
   sistema y privados intencionales del usuario.
5. **Second Pass (`second_pass/`)**
   Carril independiente para clipping local, scoring de hooks, render de
   derivados y registro explicito de optimizados para una segunda jornada.
6. **Utilidades compartidas (`video_helpers.py`)**
   Centraliza carga de config, resolucion de raices, metadatos locales y
   heuristicas de titulos.

## Resolucion de rutas
- La biblioteca de videos se toma de `scanner.video_roots` en `config.json`.
- Como fallback se admite `YOUTUBE_UPLOADER_VIDEO_ROOTS`.
- Si ninguna de las dos existe, el sistema puede inferir la raiz desde
  `scanned_videos.json`.

## Gestion de cuota de Google Cloud
- El sistema usa multiples `client_secret_X.json`.
- Si una operacion recibe `quotaExceeded (403)`, el uploader marca la llave en
  `quota_status.json` y rota a la siguiente disponible.

## Control de flujo
- **Archivo STOP:** si existe el archivo `STOP` en la raiz del subproyecto, el
  uploader se detiene antes del siguiente video.
- **Indice local:** `scanned_videos.json` guarda el estado persistente para
  evitar duplicados y conservar metadatos.
- **Carpetas operativas:** los videos subidos se mueven a
  `videos subidos exitosamente/` y los duplicados ya presentes en el canal se
  mueven a `videos_excluidos_ya_en_youtube/`.

## Doble jornada
- **Jornada 1:** `video_scanner.py`, `classify_local_videos.py` y `uploader.py`
  trabajan sobre el material fuente sin editar.
- **Jornada 2:** `second_pass/local_clip_optimizer.py` analiza y renderiza clips
  derivados en `second_pass/optimized_videos/`.
- **Registro explicito:** `second_pass/register_optimized_videos.py` es la unica
  via para incorporar optimizados a `scanned_videos.json`.

## Heuristicas del second pass
- Prioriza ventanas con cambios de escena, baja proporcion de silencio y baja
  presencia de negro.
- Si existe transcript sidecar, suma bonus por hook textual temprano.
- Genera `title_override`, `description_override` y `tags_override` para que la
  jornada 2 tenga empaque propio sin alterar el formato de la jornada 1.
