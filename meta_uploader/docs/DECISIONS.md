# Registros de Decisiones (Meta Uploader)

## D1: Meta API Endpoint vs Instagram Basic Display
- **Decisión:** Utilizar Meta Graph API v19.0.
- **Razón:** Soporta publicación automatizada de Reels para cuentas Profesionales IG y páginas FB separadas con validación.

## D2: 2 Part Upload para IG Reels
- **Decisión:** Hacer POST asíncrono al contenedor y luego un polling iterativo a `status_code` hasta que el valor sea `FINISHED`.

## D3: 3 Part Upload para FB Reels
- **Decisión:** Usar `upload_phase=start, upload (rupload), finish` usando el endpoint específico de Meta.

## D4: Clasificación Automática de Video
- **Decisión:** Usar `ffprobe` en `classify_meta_videos.py`. Relación 9:16 estricta y ventana [5-90] segundos fuerza a un contenedor de REEL.
