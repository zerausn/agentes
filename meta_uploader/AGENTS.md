# AGENTS.md - Meta Uploader

Usa `CONTEXT_FOR_AI.md` como el archivo maestro de contexto — leelo PRIMERO.
Usa `AI.md` como resumen neutral del subproyecto y `docs/` como memoria
versionada.

## Protocolo de Entrada (Obligatorio)

Antes de cambiar archivos:
- lee `CONTEXT_FOR_AI.md` (objetivos, fallas, arquitectura)
- lee `AI.md`
- lee `README.md`
- revisa `docs/ARCHITECTURE.md`, `docs/DECISIONS.md` y `docs/PROGRESS.md`
- revisa `docs/HISTORIAL_CONVERSACIONES.md` para el último estado

## Protocolo de Salida (Obligatorio)

Antes de terminar la sesión:
- actualiza `docs/PROGRESS.md` con hitos completados
- registra decisiones nuevas en `docs/DECISIONS.md`
- añade resumen de la sesión en `docs/HISTORIAL_CONVERSACIONES.md`
- si hubo cambios arquitectónicos, actualiza `docs/ARCHITECTURE.md`

## Reglas operativas

- No subas `.env`, tokens, ids reales, logs ni caches locales.
- Mantiene las rutas internas basadas en la ubicacion del archivo.
- Si cambias autenticacion, polling o limites de publicacion, actualiza
  `docs/ARCHITECTURE.md` y `docs/DECISIONS.md`.
- Si dejas trabajo complejo a medias, actualiza `docs/HANDOVER.md`.
- Si cambias el formato de `meta_uploader.log` o de los logs por plataforma,
  actualiza tambien `../scripts/monitor_realtime.py`.
