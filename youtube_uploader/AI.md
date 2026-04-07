# YouTube Uploader - AI Instructions

Este archivo complementa la guía global `Antigravity/AI.md` con reglas específicas para este proyecto.

## Comandos de Ejecución
- **Escaneo de videos:** `python video_scanner.py`
- **Limpieza de JSON:** `python clean_json.py`
- **Subida de videos:** `python uploader.py` (usa archivos .bat para facilidad).
- **Programación de borradores:** `python schedule_drafts.py`.

## Reglas de Desarrollo
- **Vanilla Python:** Usar Python 3.10+ sin frameworks pesados.
- **Logging:** Todo script debe usar el módulo `logging` y escribir en un `.log` local.
- **Cuotas:** El sistema de rotación de cuotas (`YouTubeServicePool`) es crítico y no debe ser alterado sin actualizar `docs/ARCHITECTURE.md`.
- **Exclusiones:** Antes de sugerir una subida masiva, verifica `config.json` para las listas negras de archivos y carpetas.

## Estado del Proyecto (Contexto Crucial)
- **Ruta de videos:** Protege `C:\Users\ZN-\Documents\ADM\Carpeta 1`.
- **Límite de YouTube:** Estamos bajo el error `uploadLimitExceeded` si subimos demasiados borradores. La solución es programarlos usando `schedule_drafts.py`.
- **Progreso actual:** Revisa `docs/PROGRESS.md`.
