# AI Architecture & Context Documentation (v2)
> **Target Audience:** Future AI Agents reading this repository to resume operations for `zerausn`.

## System Overview
Automated YouTube Bulk-Uploader with staggered scheduling and safety automation.

- **Objective**: Manual-free upload of theatrical registry videos.
- **Improved Strategy**: 
    1. **Config-Driven**: All settings (Tags, Description, Category, Scheduling) are in `config.json`.
    2. **Safety Automation**: Automatically sets `MadeForKids: False` and `Age Restricted: False`.
    3. **Quota Guard**: Tracks exhausted GCP projects in `quota_status.json`.
    4. **Resumable Engine**: The `uploader.py` now implements a byte-check protocol. If the network fails, it resumes from the last byte without wasting the 1,600 API quota points.
    5. **Multithreaded Scanning**: `video_scanner.py` uses `ThreadPoolExecutor` for high-speed disk traversal.

## AI Execution Instructions
1. **Config**: Check `config.json` before running. Categoría: Entretenimiento (24).
2. **Scanner**: `python video_scanner.py` (actualiza `scanned_videos.json`).
3. **Uploader**: `python uploader.py`.
    - **Naming Strategy**: `Performatic Writings | [FECHA] | ([FILENAME])`.
    - **Auth**: La primera vez con cada llave abrirá una ventana en Edge. El usuario tiene su sesión allí.
4. **Resilience**: Reintento exponencial (5 veces) ante errores de red.
5. **Deteccion de Duplicados**: El uploader no sube si la flag `uploaded` es True en `scanned_videos.json`.

