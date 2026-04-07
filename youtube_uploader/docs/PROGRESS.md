# Estado del Progreso - YouTube Uploader

Estado actual del proyecto al **06 de Abril de 2026**.

## Infraestructura del subproyecto
- [x] Ubicacion corregida a `youtube_uploader/` en la raiz del repo `agentes`.
- [x] Scripts operativos y rutas internas endurecidos para no depender de
  `agentes/agentes/youtube_uploader`.

## Estado de la biblioteca
- **Total videos encontrados en disco (Carpeta 1):** ~264 pendientes de subida
  inicial.
- **Total videos en el canal de YouTube:** 792 registrados en el ultimo
  escaneo.
- **Borradores pendientes de programar:** 147 (de un total inicial de 183).

## Logros recientes
- [x] Escaneo unificado en `C:\Users\ZN-\Documents\ADM\Carpeta 1`.
- [x] `clean_json.py` depura rutas inexistentes y aplica exclusiones nuevas.
- [x] 36 videos ya programados con fechas hasta agosto de 2026.
- [x] Los `.bat` operativos quedaron desacoplados de la ruta vieja del repo.

## Bloqueos pendientes
- **Cuota de API:** agotada en el ultimo intento; requiere esperar al reset
  diario aproximado de las 02:00 AM hora Colombia.
- **Limite del canal:** sigue activo hasta terminar de programar los borradores
  restantes.
