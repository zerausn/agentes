# Decisiones Arquitectónicas - YouTube Uploader

## 2026-04-06: Estrategia de Doble Vía (Double Track)
Se decidió implementar un calendario paralelo para Videos y Shorts para maximizar el alcance del canal. El uploader ahora detecta huecos de forma independiente por tipo.

## 2026-04-06: Clasificación de Shorts (3 Min Rule)
Se adoptó la nueva política de YouTube de permitir Shorts de hasta 3 minutos para videos verticales, actualizando los scripts de clasificación locales y del canal.

## 2026-04-06: Auditoría de Sesión
El uploader debe realizar una auditoría de la API de YouTube al iniciar para sincronizarse con el estado real de la nube, evitando duplicidad o gaps por cambios manuales en YouTube Studio.
