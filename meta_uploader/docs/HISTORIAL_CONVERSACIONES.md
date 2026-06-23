# Historial de Conversaciones - Meta Uploader

## Sesión: 2026-04-13
- **Objetivo**: Optimización del motor de subida para gran escala (2000 videos) y eliminación de duplicados persistentes.
- **Logros**:
    - Implementación de **Caché Masiva** (80 páginas de API Graph).
    - Detección de **Videos Programados** (futuros) para evitar resubidas.
    - **Limpieza Triple Nuclear**: Sincronización atómica que borra el video del disco, de las colas JSON y lo marca en el calendario.
    - **Modo Anti-Spam**: Desactivación del paralelismo de días para evitar el Error 368 de Meta.
- **Estado**: Sistema estabilizado, esperando enfriamiento de la cuenta de Meta.

## Sesión: 2026-04-15
- **Objetivo**: Limpieza de YouTube, optimización de alcance y corrección de duplicados.
- **Logros**:
    - **Rescate de YouTube**: Limpieza de 34 videos zombis y "Heavy Nudge" a videos atascados.
    - **Estrategia Dual**: Publicación automática de Teaser (60s) + Full en Instagram.
    - **Blindaje Anti-Duplicados**: Implementación de etiquetas `#teaser` y `#full` con búsquedas remotas cruzadas.
    - **Frenado de Seguridad**: El sistema ahora aborta la jornada si Meta no permite leer el catálogo remoto (deduplicación forzosa).
    - **Resiliencia API**: Reducción adaptativa de límites (limit base 5) para superar errores HTTP 500.
- **Estado**: Sistema blindado contra duplicados y fallos de API; listo para operación masiva segura.

## Sesión: 2026-04-17
- **Objetivo**: Eliminar Instagram del runner y delegarlo al vigía para evitar que fallos de IG aborten la ráfaga de Facebook.
- **Logros**:
    - **Delegación IG→Vigía**: Todas las subidas de Instagram (Reel, Feed, Story) eliminadas de `run_jornada1_normal.py`.
    - **Rescate de Ráfaga**: Si Facebook queda resuelto, la dupla se considera OK aunque IG falle o esté delegado. No más re-subidas de archivos de 1+ GB.
    - **Auto-Move y Limpieza**: Los videos originales se mueven a `ya_subidos_fb_ig/` y los temporales a `ya_subidos_ig_temp/` tras confirmarse la subida (paridad con uploader de YouTube).
    - **Ahorro de CPU**: Se elimina el deep clean (transcoding) de IG del flujo principal (~2 min/video).
- **Estado**: Runner enfocado exclusivamente en Facebook; Instagram a cargo del Vigía. Área de trabajo despejada automáticamente.

## Sesión: 2026-06-09
- **Objetivo**: Mejorar `album_diario.py` con calidad máxima y carpeta local por álbum.
- **Logros**:
    - Cambio de `-quality 92` a `-quality 100` en conversión DNG→JPEG para mínima pérdida.
    - Creación de carpeta `fotos_subidas_album/{nombre_album}/` con copia de fotos (`shutil.copy2`) al publicar álbum.
    - Confirmación de lógica: un álbum por fecha detectada en el nombre del archivo.
    - Teaser de álbum cambiado a publicación inmediata; no se agenda a las 20:00.
    - Diagnóstico de token corregido: `META_FB_PAGE_TOKEN` tenía token `USER`, no `PAGE`.
    - Page Access Token derivado y guardado en `.env`; backup local creado como `.env.bak_page_token`.
    - Preflight agregado en `album_diario.py` para derivar token de página en memoria si vuelve a aparecer un token `USER`.
    - Confirmación remota agregada: no mueve fotos a `fotos_subidas_album/Fotos YYYY-MM-DD` hasta confirmar álbum, fotos y teaser en Facebook.
    - Teaser optimizado en inglés: headline fuerte, pregunta final y carrusel distribuido priorizando fotos más pesadas.
    - Prueba viva posterior: token `PAGE` válido y con permisos correctos; lectura de página/álbumes OK; subida/borrado de foto no publicada OK; subida/borrado a álbum existente OK.
    - Fallo real reproducido: `POST /{page-id}/albums` devuelve `(#3) Application does not have the capability to make this API call` en versiones `v19.0`–`v24.0`, por capability faltante del App y no por token.
    - `album_diario.py` corregido para detenerse con diagnóstico explícito ante ese bloqueo y aceptar fallback opcional a un álbum existente mediante `META_FB_FALLBACK_ALBUM_ID` o `META_FB_FALLBACK_ALBUM_NAME`.
- **Estado**: El flujo de crear álbumes nuevos por API está bloqueado por Meta hasta habilitar/aprobar capability del App; subir a álbumes existentes sí funciona.

## Sesión: 2026-06-09 — Automatización web de álbumes y recuperación
- **Objetivo**: Dejar el flujo de álbumes diario completamente automático sin depender de crear álbumes manualmente.
- **Logros**:
    - Se agregó `photo_uploader/facebook_album_web_auto.py`: detecta fechas locales, compara con álbumes remotos y crea los faltantes por Microsoft Edge usando Chrome DevTools Protocol.
    - Se agregó `photo_uploader/subir_album_diario.sh`: lanzador Linux que primero crea álbumes faltantes por web y luego ejecuta `album_diario.py`.
    - Se confirmó en vivo que la creación por web funciona y queda confirmada por Graph API (`count >= 1`).
    - Se creó `Fotos sueltas` para agrupar fechas con una sola foto. Los álbumes individuales de una sola foto que ya se habían creado se dejaron intactos como reserva.
    - Se cambió la regla de agrupación: `1` foto -> `Fotos sueltas`; `2+` fotos -> `Fotos YYYY-MM-DD`.
    - Se corrigió el rechazo `Invalid parameter` al subir panorámicas gigantes con un pipeline JPEG seguro: `2048px` lado largo, `LANCZOS`, `sRGB`, EXIF aplicado y `quality=88`.
    - Se agregó recuperación contra interrupciones: el script lista fotos remotas por caption `Archive frame`, salta ya subidas, detecta teaser existente por `published_posts` y evita duplicados.
    - Se confirmó en vivo `Fotos sueltas` con 21 fotos, teaser de 5 fotos y archivado local tras confirmación.
    - Se confirmó en vivo que álbumes pequeños de `2-3` fotos publican teaser con las disponibles, quedan confirmados y se archivan.
- **Estado**: El flujo ya verifica listado de fechas y crea álbumes automáticamente. La corrida quedó detenida a pedido del usuario durante `Fotos 2025-10-24`; se puede continuar ejecutando `photo_uploader/subir_album_diario.sh` y reanudará sin duplicar.
