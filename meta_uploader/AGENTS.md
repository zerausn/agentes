# AGENTS.md - Meta Uploader

Usa `AI.md` como resumen neutral del subproyecto y `docs/` como memoria
versionada.

## Entrada obligatoria

Antes de cambiar archivos:
- lee `AI.md`
- lee `README.md`
- revisa `docs/ARCHITECTURE.md`, `docs/DECISIONS.md` y `docs/PROGRESS.md`

## Reglas operativas

- No subas `.env`, tokens, ids reales, logs ni caches locales.
- Mantiene las rutas internas basadas en la ubicacion del archivo.
- Si cambias autenticacion, polling o limites de publicacion, actualiza
  `docs/ARCHITECTURE.md` y `docs/DECISIONS.md`.
- Si dejas trabajo complejo a medias, actualiza `docs/HANDOVER.md`.
