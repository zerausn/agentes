# Decisiones Arquitectonicas - YouTube Uploader

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

## 2026-04-06: Automatizacion en la raiz del repo para el subproyecto anidado
- Contexto: `agentes/youtube_uploader` vive dentro de este repo, pero no es un
  repo Git separado.
- Decision: la capa `.antigravity/automation.json` se registra en la raiz del
  repo `agentes` y valida sintaxis del subproyecto anidado y del bootstrap
  `scripts/init-agents.ps1`.
