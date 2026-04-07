# Estado de Progreso - Repo agentes

## Infraestructura del repo
- `youtube_uploader/` ya vive en la raiz del repo contenedor.
- Se eliminaron las referencias operativas al nesting accidental
  `agentes/agentes/youtube_uploader`.
- La automatizacion raiz ahora valida `youtube_uploader/`, `meta_uploader/` y
  `scripts/init-agents.ps1`.
- `meta_uploader/` ya tiene contexto local minimo y setup base, aunque su
  implementacion funcional sigue en desarrollo.

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
