# Decisiones Arquitectonicas - Repo agentes

## 2026-04-20: Mantener hibernacion desactivada en Windows para dual boot con Parrot OS
- Contexto: en esta maquina el usuario necesita acceder desde Parrot OS a la
  particion NTFS de Windows. La sesion mostro `HiberbootEnabled = 0`, pero la
  hibernacion seguia activa, existia `C:\hiberfil.sys` y el registro de
  `Kernel-Power` mostraba entradas recientes `Event ID 42` por
  `Hibernate from Sleep`.
- Decision: desactivar la hibernacion del sistema (`powercfg /hibernate off`)
  y mantener el arranque rapido apagado para evitar que Linux vea la unidad de
  Windows como hibernada o en estado inseguro.
- Consecuencia: Windows ya no ofrecera el modo `Hibernar` mientras esta
  compatibilidad dual boot sea un requisito operativo.

## 2026-04-06: Corregir nesting accidental de `youtube_uploader`
- Contexto: el subproyecto estaba fisicamente dentro de `agentes/agentes/`,
  mientras otros subproyectos funcionales del repo viven en la raiz.
- Decision: mover `youtube_uploader` a `youtube_uploader/` en la raiz del repo
  y actualizar automatizacion, documentacion y scripts para no depender de la
  ruta vieja.
- Consecuencia: cualquier referencia a `agentes/youtube_uploader` queda
  obsoleta y debe tratarse como deuda ya cerrada.

## 2026-04-23: Ecosistema Shadow (Linux vs Windows) para Agentes
- Contexto: Con la desactivación de hibernación/fast-boot en Windows, el equipo usa Parrot OS (Linux) para ciertas tareas críticas, lo que expuso la dependencia de todo el repositorio a scripts de PowerShell (`.ps1`).
- Decision: Crear una jerarquía de scripts equivalente en `scripts/linux/` (`iniciar_agentes.sh`, `start_agent_meta.sh`, `subida_fb_fotos.sh`, etc.) para garantizar "paridad operativa". Los entornos virtuales (`.venv`) y rutas se construyen de forma agnóstica al OS.
- Consecuencia: Las futuras automatizaciones deben entregarse con scripts dobles: un `.ps1` para Windows y un `.sh` para Linux que invoquen al mismo entrypoint Python.

## 2026-04-23: Entorno Linux para la Migracion YouTube -> Facebook (Vigía 4K)
- Contexto: El usuario requiere automatizar la descarga de ~580 videos desde YouTube a su disco duro para ser pasados a Meta, enfrentando limites de cuota de API (Error 403) y bloqueos HLS (SABR Streaming). Por seguridad con BitLocker, esta operacion corre en Parrot OS sobre Microsoft Edge for Linux y herramientas open-source nativas, de forma agnostica al Windows original.
- Decision: El agente migrador se creo como herramienta exclusiva de Linux. Se dividio el proceso de descarga `yt-dlp` en 2 tracks asíncronos (video puro + audio puro) con clientes independientes (`ios`, `tv`, `web`, `mweb`).
- Consecuencia: Requerimos empaquetar de vuelta con `ffmpeg` local. Los reintentos por fragmento se redujeron para forzar rotacion rapida de clientes y evadir soft-bans de IP por parte de YouTube.

## Estrategia YouTube Teaser Uploader (2026-04-21)

- **Aislamiento Total:** Se decidio que el Agente de Teasers sea un script 100% independiente (`teaser_uploader.py`) en lugar de añadir flags a `uploader.py`. Esto garantiza que los teasers/shorts jamas contaminen el sistema de playlists de los crudos largos.
- **Monitoreo de Procesamiento Asincrono:** Para evitar videos "zombies" (trabados en procesamiento HD), se implemento un sistema de hilos (`threading`) que verifica el estado del video en YouTube durante 10 minutos (20 intentos) en paralelo. Esto permite que la subida principal continue sin esperas bloqueantes.
- **Politica de Nombres Limpios:** Se usa Regex agresivo para eliminar `ig_compat_` y `slice_60s_` pero preservando el timestamp numerico original (`\d{8}_\d{6}`).
- **Ratio de Publicacion 1:3:** Se establecio que el bot publique 1 video de forma inmediata (`public`) y los siguientes 3 de forma programada (`private` con `publishAt`), repitiendo el ciclo para mantener relevancia en el feed sin saturar.

## Optimizacion Photo Uploader (2026-04-21)

- **Evitar Re-procesamiento 4K:** En lugar de renderizar el Reel de 30s desde fotos originales 10 veces, se procesa cada foto una sola vez a un mini-Reel de 5s, se sube, y luego se usan esos mini-MP4s para "coser" el Reel combinado usando el concat demuxer de FFmpeg.
- **Persistencia de Assets:** Los Reels individuales generados se conservan en `reels_generados_fb` para su re-uso optimo en Instagram u otras redes.

## 2026-04-06: Los docs raiz quedan reservados para el repo contenedor
- Contexto: la memoria del repo raiz habia quedado mezclada con estado operativo
  especifico de `youtube_uploader`.
- Decision: las decisiones y el progreso de cada subproyecto deben vivir en su
  propio `docs/`, mientras `docs/` en la raiz se usa para reglas del contenedor,
  automatizacion compartida y estructura del workspace.

## 2026-04-06: Estrategia de Doble Via (Double Track)
Se decidio implementar un calendario paralelo para Videos y Shorts para
maximizar el alcance del canal. El uploader ahora detecta huecos de forma
independiente por tipo.

## 2026-04-06: Clasificacion de Shorts (3 Min Rule)
Se adopto la nueva politica de YouTube de permitir Shorts de hasta 3 minutos
para videos verticales, actualizando los scripts de clasificacion locales y
del canal.

## 2026-04-06: Prefijo de Titulos (PW)
A solicitud del usuario, se cambio el prefijo de los titulos de
"Performatic Writings" a "PW" para mayor brevedad y consistencia visual en el
canal.

## 2026-04-06: Automatizacion en la raiz del repo para los subproyectos
- Contexto: `youtube_uploader` y `meta_uploader` viven dentro de este repo,
  pero no son repos Git separados.
- Decision: la capa `.antigravity/automation.json` se registra en la raiz del
  repo `agentes` y valida sintaxis de los subproyectos funcionales y del
  bootstrap `scripts/init-agents.ps1`.

## 2026-04-09: Monitor de logs en tiempo real para Meta y YouTube
- Contexto: el usuario necesita observar en consola el avance de Meta Facebook,
  Meta Instagram y YouTube sin depender de preguntar a la IA cada vez.
- Decision: agregar `scripts/monitor_realtime.py` como herramienta de solo
  lectura sobre los logs locales, mas un launcher `.bat` reutilizable.
- Consecuencia: si cambian los formatos de `meta_uploader.log`,
  `meta_uploader_facebook.log`, `meta_uploader_instagram.log` o `uploader.log`,
  tambien debe actualizarse el monitor para no romper la observabilidad.

## 2026-04-10: Unificar la convención de Meta
- Contexto: el usuario decidio que "sube videos a Meta" debe apuntar al flujo
  programado vigente, y que el carril previo de Meta pase a llamarse
  "videos optimizados".
- Decision: documentar `meta_uploader/schedule_jornada1_supervisor.py` como
  entrypoint humano recomendado para Meta, dejando `run_jornada1_normal.py`
  como constructor/runner base y `meta_uploader.py` como capa de subida.
- Consecuencia: los docs del repo deben usar "videos optimizados" para el
  carril `second_pass/`, aunque el folder tecnico siga existiendo por ahora.
