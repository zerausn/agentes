# Sistema de Agentes Coordinados - AI Instructions

Este `AI.md` aplica al repo raiz `agentes`, no al subproyecto
`agentes/youtube_uploader`. Si trabajas dentro de `agentes/youtube_uploader`,
usa el contexto local de ese subproyecto como fuente mas especifica.

## Que es este repo

Este repo contiene propuestas, configuraciones, scripts y documentacion para
orquestar multiples agentes de desarrollo, ademas de algunos subproyectos
anidados como `youtube_uploader`.

## Antes de editar

- Lee `AGENTS.md` en la raiz del repo.
- Revisa `README.md`.
- Rehidrata estado desde `docs/DECISIONS.md`, `docs/PROGRESS.md` y
  `docs/HISTORIAL_CONVERSACIONES.md`.
- Si trabajas en un subproyecto con su propio `AGENTS.md` o `AI.md`, el
  contexto mas cercano tiene prioridad.

## Mapa rapido

- `agentes/youtube_uploader/`: automatizacion de YouTube con contexto propio
- `configs/`: configuraciones de agentes
- `scripts/`: automatizaciones y bootstrap
- `nemoclaw/`: contexto operativo y documentacion separada
- `docs/`: estado del sistema de agentes coordinados

## Reglas

- No mezcles contexto del repo raiz con el de subproyectos anidados.
- No cambies decisiones registradas sin actualizar `docs/DECISIONS.md`.
- Si una sesion compleja queda en pausa, deja nota en `docs/HANDOVER.md`.
- No subas secretos, tokens ni archivos locales.
