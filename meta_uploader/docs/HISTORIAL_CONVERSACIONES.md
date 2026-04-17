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
