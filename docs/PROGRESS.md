# Estado de Progreso - Repo agentes

## Infraestructura del repo
- Se resolvio la parte de hibernacion de una incidencia operativa de dual boot
  Windows 11 + Parrot OS en esta maquina: Windows quedo con hibernacion
  desactivada, `HiberbootEnabled` confirmado en `0` y sin `hiberfil.sys`.
- En el mismo diagnostico se confirmo que `C:` sigue con BitLocker
  `FullyEncrypted` (`XTS-AES 128`) aunque la proteccion esta en `Off`; por eso
  el acceso transparente desde Parrot sigue requiriendo una decision aparte:
  descifrar completamente `C:` o usar una ruta Linux compatible con BitLocker.
- Se dejo trazabilidad local de la correccion en
  `workspace-local/fix_dualboot_windows_access.ps1` y su log asociado.
- **Ecosistema Dual-Boot Consolidado:** Se construyo una suite paralela de scripts Bash ubicados en `scripts/linux/` para proveer paridad operativa en Parrot OS frente a los scripts PowerShell originales de Windows.
  - Scripts generados: `iniciar_agentes.sh`, `mejorador.sh`, `monitor_logs.sh`, `procesamiento_masivo.sh`, `start_agent_meta.sh`, `start_agent_youtube.sh`, `subida_fb_fotos.sh`, `subida_yt_teaser.sh`, `vigia_meta.sh`.
  - El sistema detecta y activa automaticamente los entornos virtuales correctos para ambos ecosistemas.
- `youtube_uploader/` ya vive en la raiz del repo contenedor.
- Se eliminaron las referencias operativas al nesting accidental
  `agentes/agentes/youtube_uploader`.
- La automatizacion raiz ahora valida `youtube_uploader/`, `meta_uploader/` y
  `scripts/init-agents.ps1`.
- `meta_uploader/` ya tiene contexto local minimo y setup base, aunque su
  implementacion funcional sigue en desarrollo.
- Se agrego un monitor de logs en tiempo real para Meta y YouTube en
  `scripts/monitor_realtime.py`, con launcher `.bat` y nota para futuras IAs.
- La convencion operativa de Meta quedo unificada en documentacion: "sube
  videos a Meta" significa usar `schedule_jornada1_supervisor.py`, y el carril
  previo de Meta pasa a llamarse "videos optimizados" en los docs.

## Sincronizador Vigía: YouTube -> Facebook (Linux/4K)
- Se implemento `youtube_to_fb_watcher.py` en `youtube_uploader/` especificamente para el entorno **Linux (Parrot OS)**.
- **Filtrado:** Identifica videos publicos subidos antes del 1 de marzo de 2026 que aun no estan en `sync_history.json`.
- **Estrategia Anti-403 (SABR Streaming):** Para evadir los bloqueos persistentes de YouTube al descargar fragmentos (HLS/m3u8), se implemento una arquitectura de descargas de 3 pasos usando `yt-dlp` y `ffmpeg`:
  1. Descarga del video 4K (solo video) rotando clientes (`ios`, `tv`, `web`).
  2. Descarga del audio usando los mismos clientes con cookies de Microsoft Edge.
  3. Fusión (`ffmpeg -movflags +faststart`).
- **Resiliencia:** Reintentos limitados por fragmento (`--fragment-retries`, `--retries`) para permitir `fail-fast` y saltar al siguiente cliente `yt-dlp` disponible.
- **Archivos de control:** Trabaja de la mano con `checklist_sincronizacion.md` (como backup visual del lote) y guarda en el disco dual (`D69493CF9493B08B`).

## YouTube Teaser Uploader (Nuevo Agente)
- Se implemento `teaser_uploader.py` como un agente independiente y aislado.
- **Funcionalidad:** Recicla material de descarte de IG (60s slices) y los sube a YouTube.
- **Aislamiento:** No interactua con el sistema de playlists de los crudos largos.
- **Monitoreo:** Implementacion de threads en paralelo para verificar el procesamiento HD y evitar videos "zombies" sin bloquear la cola de subida.
- **Limpieza:** Logica de regex para limpiar prefijos `slice_` e `ig_compat_` manteniendo la fecha original del video.
- **Ratio:** Algoritmo 1:3 (1 publicado inmediato, 3 programados a futuro).
- **Lanzadores:** Acceso directo desde el Escritorio con `EJECUTAR_SUBIDAYoutube_Teaser.bat`.

## Optimizacion Meta (Photo Uploader)
- Rediseño del pipeline para evitar doble procesamiento de fotos 4K.
- Generacion de Reels individuales de 5s y concatenacion ultra-rapida de Reel combinado de 30s usando demuxer de FFmpeg.
- Carpeta de salida persistente para Reels generados: `reels_generados_fb`.


## Seguimiento operativo heredado de `youtube_uploader`

## Resumen de Inventario (Carpeta 1)
- Shorts detectados: 96
- Videos largos detectados: 24
- Procesados en esta sesion: 2 (y un tercero en curso)

## Calendario de Publicacion (Gaps llenos)
- 2026-04-06: OK (V:1 S:1)
- 2026-04-07: Short programado (borrador previo o nuevo)
- 2026-04-08: Short programado (ID: ctntHGdGY-o)
- 2026-04-09: Short programado (ID: Z9_qrkXMkHo - pendiente confirmar)

## Proximos huecos a llenar
- Shorts faltantes del 10 de abril al 4 de mayo.
- Videos largos a partir del 5 de mayo (cuando se agoten los ya programados).

## Estado de la cuota (4 cuentas)
- Cuenta 0: en uso.
- Cuentas 1, 2 y 3: disponibles.

## Infraestructura de automatizacion
- `.antigravity/automation.json` agregado en la raiz del repo.
- Workflow `agent-validate.yml` agregado para validar PRs sin depender solo
  del contexto Markdown.
- El flujo de publicacion automatica ya puede validar el subproyecto anidado
  antes de abrir una rama o PR.
