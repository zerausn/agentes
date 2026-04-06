# YouTube Uploader - AI Instructions

Este proyecto automatiza la subida y programación de videos y Shorts siguiendo una estrategia de "Doble Vía" (1 Video + 1 Short diario).

## Convenciones del Proyecto
1.  **Clasificación de Shorts:** Se rige por la regla de YouTube (Oct 2024): 
    - Vertical/Cuadrado: Hasta 180s.
    - Horizontal: Hasta 60s.
2.  **Estrategia de Programación:** 
    - Priorizar el llenado de huecos (Gaps) en el calendario detectados al inicio de cada sesión.
    - Mantener un balance de 1:1 diario.
3.  **Mecanismos de Control:**
    - `STOP`: Archivo para detener limpiamente el uploader.
    - `scanned_videos.json`: Base de datos local de seguimiento (Ignorada por Git).

## Arquitectura de Memoria
- `AI.md`: Este archivo.
- `docs/`: Documentación técnica y estado del proyecto.
- `docs/DECISIONS.md`: Registro de decisiones arquitectónicas.
- `docs/PROGRESS.md`: Estado actual del inventario y programación.
