# Decisiones Arquitectonicas - Repo agentes

## 2026-04-06: Corregir nesting accidental de `youtube_uploader`
- Contexto: el subproyecto estaba fisicamente dentro de `agentes/agentes/`,
  mientras otros subproyectos funcionales del repo viven en la raiz.
- Decision: mover `youtube_uploader` a `youtube_uploader/` en la raiz del repo
  y actualizar automatizacion, documentacion y scripts para no depender de la
  ruta vieja.
- Consecuencia: cualquier referencia a `agentes/youtube_uploader` queda
  obsoleta y debe tratarse como deuda ya cerrada.

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
