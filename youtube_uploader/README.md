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

## Mantenimiento de Credenciales (Renovacion de Tokens)

Si recibes errores de `invalid_grant` o tokens expirados, puedes renovar todas las llaves de una vez sin esperar a que el uploader falle:

1. Borrar los tokens viejos: `Remove-Item credentials/token_*.json`
2. Generar nuevos tokens manualmente uno por uno:
   ```powershell
   python auth_manager.py 1
   python auth_manager.py 2
   python auth_manager.py 3
   python auth_manager.py 4
   ```
   Cada comando abrira una ventana en el navegador para la autorizacion.

## Estrategia y Seguridad

- **Ciclo de 400 días**: El sistema gestiona un calendario de largo plazo en `meta_calendar.json`.
- **Bandera de Seguridad**: Requiere `META_ENABLE_UPLOAD=1` en el archivo `.env`. El sistema carga este archivo automáticamente.
- **Cierre de Handles**: El uploader ahora cierra explícitamente todos los archivos después de la subida para evitar bloqueos en Windows.
- **Higiene Automática**: Se incluye `periodic_mover.py`, un servicio que organiza videos finalizados y libera espacio automáticamente.
- **Monetización Global**: Configurado por defecto a las 14:00 (Hora Col) para maximizar CPM global.

Para más detalles sobre la operación diaria, consulta el manual maestro en [MAINTENANCE.md](../MAINTENANCE.md).

## Documentacion Completa
Ver [AI.md](AI.md) y la carpeta [docs](docs).

**Para futuras IAs**: Si estás trabajando en este proyecto, revisa SIEMPRE el archivo [TODO.md](TODO.md) antes de empezar para conocer las tareas críticas pendientes, los bloqueadores de desarrollo y las mejoras técnicas planificadas.

## Privacidad
Los archivos `config.json`, `credentials/` y `*.log` estan excluidos de Git.
