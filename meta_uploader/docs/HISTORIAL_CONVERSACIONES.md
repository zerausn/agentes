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
- **Estado**: Listo para prueba controlada; no se lanzó la subida masiva completa.
