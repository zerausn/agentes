# TikTok Uploader VIVO — AI Instructions

**CLON ESTRICTAMENTE SEPARADO — NO TOCAR CODIGO DEL NOTE9**

## Reglas de oro
1. Todo cambio en `agentes/tiktok_uploader/vivo/` es exclusivo del VIVO.
2. No modificar `agentes/tiktok_uploader/tiktok_evacuador_720.py` — ese archivo es del Note9.
3. El clon VIVO tiene su propia copia del evacuador en `/sdcard/Antigravity/agentes/tiktok_uploader/` dentro del VIVO.
4. Las coordenadas de pantalla del VIVO (1080x2408) son diferentes del Note9 (720x1480).
5. No compartir tokens, secrets, ni config.env entre Note9 y VIVO.

## Stack VIVO
- Termux con ADB USB
- Python 3 via Termux
- Sin ngrok (no necesita tunnel — usa ADB local USB)
- Android 13 (SDK 33)
- Resolucion nativa 1080x2408

## Archivos clave en VIVO
- `/data/data/com.termux/files/home/agentes/tiktok_uploader/tiktok_evacuador_720.py` — script principal
- `/sdcard/Antigravity/subidos a facebbok/` — videos pendientes
- `/sdcard/Antigravity/subidos a tiktok/` — videos publicados
- `/sdcard/Antigravity/.state/` — estado y lock files
- `/sdcard/Antigravity/widget_logs/6_SUBIR_TIKTOK720.log` — logs

## Sync workflow
1. PC → VIVO via `vivo/sync_to_vivo.sh` (ADB USB)
2. VIVO interno: `termux/deploy.sh` copia sdcard → home de Termux
3. Vigia: `termux/vigia_vivo.sh` ejecuta loop 720s o widget Termux
