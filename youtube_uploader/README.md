# YouTube Uploader - Performatic Writings

Sistema automatizado de subida de videos artisticos a YouTube.

## Inicio Rapido

```powershell
# 1. (Primera vez) Copiar y configurar:
Copy-Item config.example.json config.json
# Editar config.json:
# - scanner.video_roots: una o varias carpetas de videos
# - default_metadata: descripcion, tags, etc.

# 2. Escanear biblioteca local:
python video_scanner.py

# 3. Clasificar metadatos locales:
python classify_local_videos.py

# 4. Sincronizar con el canal y mover duplicados ya existentes:
python check_channel_videos.py

# 5. Limpiar entradas obsoletas del indice:
python clean_json.py

# 6. Subir:
python uploader.py
```

Si prefieres no guardar rutas en `config.json`, puedes definirlas con la variable
de entorno `YOUTUBE_UPLOADER_VIDEO_ROOTS`, separando varias carpetas con `;`.

## Segunda Jornada de Clipping Local

La subida cruda sigue igual. Las mejoras locales viven en [second_pass/README.md](second_pass/README.md):

```powershell
python second_pass/local_clip_optimizer.py `
  --input "C:\ruta\video.mp4" `
  --render-top 1 `
  --emit-queues

python second_pass/register_optimized_videos.py `
  --queue second_pass/queues/pendientes_second_pass_hook_shorts.json

python uploader.py
```

Ese flujo genera clips optimizados en carpeta separada y solo los incorpora al
indice cuando lanzas el registro explicito de la jornada 2.

## Parada de Emergencia

```powershell
New-Item STOP -ItemType File
```

Para reanudar: `Remove-Item STOP`

## Documentacion Completa
Ver [AI.md](AI.md) y la carpeta [docs](docs).

## Privacidad
Los archivos `config.json`, `credentials/` y `*.log` estan excluidos de Git.
