# Arquitectura del repo `agentes`

## Proposito

Este repo no es un solo producto ejecutable. Es un contenedor de:
- propuestas para un sistema de agentes coordinados
- configuraciones y scripts de automatizacion
- documentacion operacional
- subproyectos anidados con vida propia

## Componentes principales

- `configs/`: configuracion de agentes y entorno
- `scripts/`: bootstrap y automatizacion
- `nemoclaw/`: contexto y documentacion especializada
- `agentes/youtube_uploader/`: subproyecto con memoria y docs propios

## Regla de contexto

El contexto del repo raiz no debe eclipsar a un subproyecto anidado.
Si una tarea ocurre dentro de `agentes/youtube_uploader`, mandan sus propios
`AI.md`, `AGENTS.md` y `docs/`.
