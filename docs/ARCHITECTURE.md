# Arquitectura del repo `agentes`

## Proposito

Este repo no es un solo producto ejecutable. Funciona como contenedor de:
- propuestas para un sistema de agentes coordinados
- configuraciones y scripts de automatizacion
- documentacion operacional del repo
- subproyectos funcionales con vida propia

## Componentes principales

- `configs/`: configuracion de agentes y entorno
- `scripts/`: bootstrap y automatizacion
- `nemoclaw/`: contexto y documentacion especializada
- `youtube_uploader/`: subproyecto funcional de YouTube con contexto propio
- `meta_uploader/`: subproyecto funcional de Meta en desarrollo

## Regla de contexto

El contexto del repo raiz no debe eclipsar a un subproyecto con memoria local.
Si una tarea ocurre dentro de `youtube_uploader`, mandan su `AGENTS.md`,
su `AI.md` y su `docs/`.

## Regla de ubicacion

Los subproyectos funcionales de este repo viven en la raiz del contenedor.
La ruta historica `agentes/youtube_uploader` fue un error de nesting y ya no
debe usarse como referencia operativa ni documental.
