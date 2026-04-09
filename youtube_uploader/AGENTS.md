# AGENTS.md - YouTube Uploader

Usa `AI.md` como resumen neutral del subproyecto y `docs/` como memoria
versionada.

## Entrada obligatoria

Antes de cambiar archivos:
- lee `AI.md`
- lee `README.md`
- revisa `docs/ARCHITECTURE.md`, `docs/DECISIONS.md` y `docs/PROGRESS.md`

## Reglas operativas

- No subas secretos, tokens OAuth, `config.json`, `credentials/` ni logs.
- Mantiene las rutas internas basadas en la ubicacion del archivo; no dependas
  de rutas absolutas `C:\Users\...` para localizar este subproyecto.
- Si cambias la rotacion de credenciales, el archivo `STOP` o la logica de
  programacion, actualiza `docs/ARCHITECTURE.md` y `docs/DECISIONS.md`.
- Si dejas trabajo operativo a medias, actualiza `docs/HANDOVER.md`.
- Si cambias el formato de `uploader.log` o del progreso que imprime
  `uploader.py`, actualiza tambien `../scripts/monitor_realtime.py`.
