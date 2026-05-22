# AGENTS.md - Sistema de Agentes Coordinados

Usa `AI.md` como resumen neutral del repo y `docs/` como memoria versionada.

## Entrada obligatoria

Antes de cambiar archivos:
- lee `AI.md`
- lee `README.md`
- revisa `docs/DECISIONS.md` y `docs/PROGRESS.md`
- si vas a trabajar en `youtube_uploader`, cambia al contexto local de ese
  subproyecto porque es mas especifico que este archivo

## Reglas operativas

- No subas secretos ni archivos locales.
- No cambies decisiones documentadas sin registrar el motivo.
- Si dejas trabajo complejo a medias, actualiza `docs/HANDOVER.md`.
- Si cambias los formatos de salida de `meta_uploader` o `youtube_uploader`,
  ajusta tambien `scripts/monitor_realtime.py` para que el monitoreo no se rompe.

## Workflow específico para teaser generation y upload

### Generación de teasers (en dispositivo S24)

1. **Clasificación automática de crudos**:
   ```bash
   # Desde el dispositivo (Termux o run-as com.termux):
   cd /sdcard/Antigravity/agentes/youtube_uploader
   python3 teaser_generator.py
   ```
   - Genera/actualiza `/sdcard/Antigravity/classification_db.json` (TTL 24h)
   - Clasifica cada video como HDR/SDR y determina pipeline (remux/HW transcode/SW transcode)
   - Crea teasers en `/sdcard/Antigravity/teasers_pendientes/`

2. **Verificar generación**:
   ```bash
   ls -lh /sdcard/Antigravity/teasers_pendientes/
   cat /sdcard/Antigravity/bench/generation_results.json
   ```

### Subida a YouTube

1. **Validar credenciales** (opcional pero recomendado):
   ```bash
   cd /data/data/com.termux/files/home/agentes/youtube_uploader
   python3 auth_manager.py 1  # prueba una llave
   ```

2. **Ejecutar subida** (usa el widget o ejecuta directamente):
   ```bash
   # Opción 1: Widget (recomendado en dispositivo)
   # Ejecutar 3_SUBIR_TEASERS_YT.sh desde widget de Termux
   
   # Opción 2: Ejecución manual
   cd /sdcard/Antigravity/agentes/youtube_uploader
   /data/data/com.termux/files/usr/bin/python3 teaser_uploader.py \
       > /sdcard/Antigravity/bench/yt_upload.log 2>&1 &
   ```

3. **Monitoreo de progreso** (cada 3 minutos):
   ```bash
   watch -n 180 "grep -E 'Progreso:|Subida completada|Error HTTP' /sdcard/Antigravity/bench/yt_upload.log"
   ```
   - Busca líneas como `Progreso: XX%` para calcular ETA
   - Busca `quotaExceeded` o `rateLimitExceeded` para rotación automática de llaves

### Subida a Facebook/Meta

1. **Ejecutar subida a Facebook**:
   ```bash
   # Verificar existencia de meta_uploader
   ls /sdcard/Antigravity/agentes/meta_uploader/
   
   # Ejecutar (ajustar según script disponible)
   cd /sdcard/Antigravity/agentes/meta_uploader
   python3 meta_uploader.py > /sdcard/Antigravity/bench/fb_upload.log 2>&1 &
   ```
   - Alternativamente usar widget `4_VIGIA_FACEBOOK.sh` si existe

2. **Monitoreo de Facebook**:
   ```bash
   watch -n 180 "tail -20 /sdcard/Antigravity/bench/fb_upload.log"
   ```

### Manejo de errores comunes

1. **Quota excedida en YouTube**:
   - El sistema rota automáticamente a la siguiente llave disponible
   - Verificar `/sdcard/Antigravity/bench/quota_status.json`
   - Si todas las llaves están agotadas, esperar hasta mañana o renovar tokens

2. **Errores de formato/HDR**:
   - Revisar logs FFmpeg en `/sdcard/Antigravity/bench/*_teaser_*.fflog`
   - Si se rechaza por HDR, considerar:
     a) Regenerar teaser forzando 8-bit: `-pix_fmt yuv420p`
     b) Aplicar tonemapping con filtros zscale
     c) Subir como HEVC 10-bit si YouTube lo acepta

3. **Problemas de credenciales/token**:
   - Verificar expiración en archivos `token_*.json`
   - Renovar con `auth_manager.py <numero>`
   - Asegurarse de tener scopes de upload

### Rutas importantes en el dispositivo

- **Teasers generados**: `/sdcard/Antigravity/teasers_pendientes/`
- **Logs de generación**: `/sdcard/Antigravity/bench/generation_results.json` y `*_teaser_*.fflog`
- **Logs de YouTube**: `/sdcard/Antigravity/bench/yt_upload.log`
- **Logs de Facebook**: `/sdcard/Antigravity/bench/fb_upload.log`
- **Credenciales YouTube**: `/data/data/com.termux/files/home/agentes/youtube_uploader/credentials/`
- **Clasificación persistente**: `/sdcard/Antigravity/classification_db.json`

### Comandos útiles de ADB

```bash
# Listar teasers pendientes
adb shell ls -lh /sdcard/Antigravity/teasers_pendientes/

# Ver logs en tiempo real
adb shell "run-as com.termux tail -f /sdcard/Antigravity/bench/yt_upload.log"

# Contar teasers subidos
adb shell "run-as com.termux grep -c 'Subida Teaser completada' /sdcard/Antigravity/bench/yt_upload.log"

# Limpiar procesos colgados
adb shell "run-as com.termux pkill -f teaser_uploader.py"
```