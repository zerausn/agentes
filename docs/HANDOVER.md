# Handover

## Estado de proveedores IA (2026-09-06)

La documentacion completa esta en `docs/PROVEEDORES_IA_CODEX_2026-09-06.md`.

- OpenRouter y Groq tienen credenciales validas y Responses API comprobada.
- DeepSeek requiere saldo para generar respuestas.
- B.AI gratuito se usa por `chat/completions`, no directamente desde Codex.
- Antes de una prueba de agente completa en Codex, reparar o actualizar la
  instalacion local: `state_5.sqlite` reporta una migracion incompatible y el
  cache de plugins/MCP emite advertencias. No borrar esos datos sin respaldo y
  una decision explicita.
- Antes de cerrar la implementacion de Antigravity Manager, actualizar Rust a
  `1.88+` y ejecutar `cargo check`.

## Estado actual (2026-06-18)

**TikTok Uploader**: App review rechazada x2. Hay que resolver 3 issues y resubmit.
Ver `tiktok_uploader/docs/HANDOVER.md` para detalles operativos.

El resto de subproyectos (youtube_uploader, meta_uploader) no tienen handover
bloqueante.

## Si retomas trabajo en este repo

- lee `README.md`
- lee `docs/DECISIONS.md`
- lee `docs/PROGRESS.md`
- si la tarea real vive en un subproyecto anidado, cambia a ese contexto
