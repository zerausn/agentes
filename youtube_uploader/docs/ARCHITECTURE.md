# Arquitectura del Sistema - YouTube Uploader

Este documento describe el diseno tecnico del automatizador de videos para el
canal "Performatic Writings".

## Ubicacion del subproyecto
- Este subproyecto vive en `youtube_uploader/` dentro de la raiz del repo
  contenedor `agentes`.
- Los scripts deben resolver su directorio base desde `__file__` para no
  depender de la ruta historica `agentes/agentes/youtube_uploader`.

## Componentes principales
1. **Scanner (`video_scanner.py`)**
   Escaneo multihilo de directorios, filtrado por tamano/extensiones y
   exclusiones por carpeta, archivo y patron.
2. **Uploader (`uploader.py`)**
   Motor de subida fraccionada con reintentos, rotacion de credenciales y
   mecanismo de parada de emergencia mediante `STOP`.
3. **Scheduler (`schedule_drafts.py`)**
   Programa borradores a un video por dia a las 17:45 hora Colombia y distingue
   entre borradores propios y privados intencionales.

## Gestion de cuota de Google Cloud (GCP)
- El sistema usa un `YouTubeServicePool` que carga multiples
  `client_secret_X.json`.
- Si una operacion recibe `quotaExceeded (403)`, el pool rota automaticamente a
  la siguiente credencial disponible.
- Se usan scopes de lectura y escritura (`upload`, `readonly`, `force-ssl`).

## Control de flujo
- **Archivo STOP:** si existe el archivo vacio `STOP` en la raiz del
  subproyecto, el motor se detiene limpiamente.
- **Base de datos local:** `scanned_videos.json` guarda el estado persistente de
  cada archivo para evitar duplicados.
