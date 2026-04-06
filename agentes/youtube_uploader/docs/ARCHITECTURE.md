# Arquitectura del Sistema - YouTube Uploader

Este documento describe el diseño técnico del automatizador de videos para el canal "Performatic Writings".

## Componentes Principales
1.  **Scanner (`video_scanner.py`):**
    - Escaneo multihilo de directorios.
    - Filtrado por tamaño (>100MB) y extensiones de video.
    - Sistema de exclusión por carpeta, archivo único y patrones de texto.
2.  **Uploader (`uploader.py`):**
    - Motor de subida fraccionada con reintentos automáticos.
    - Integración con el sistema de rotación de credenciales.
    - Mecanismo de parada de emergencia (`STOP`).
3.  **Scheduler (`schedule_drafts.py`):**
    - Gestión masiva de borradores.
    - Identifica videos sin fecha de publicación y los programa a 1 por día a las 17:45 Col.
    - Filtra inteligentemente entre "Borradores" (nuestras subidas) y "Videos Privados" (del usuario).

## Gestión de Cuota de Google Cloud (GCP)
- El sistema usa un `YouTubeServicePool` que carga múltiples `client_secret_X.json`.
- Si una operación recibe `quotaExceeded (403)`, el pool rota automáticamente a la siguiente credencial disponible.
- Se implementan Scopes de lectura y escritura (`upload`, `readonly`, `force-ssl`).

## Control de Flujo
- **Archivo STOP:** Si existe el archivo vacío `STOP` en la raíz, el motor se detiene limpiamente.
- **Base de Datos Local:** `scanned_videos.json` guarda el estado persistente de cada archivo para evitar duplicados.
