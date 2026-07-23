# AGENTS.md — TikTok Uploader VIVO (Clon)

**IMPORTANTE: Este es un CLON independiente para VIVO V2058.**
**NO modificar la instalacion del Note9 (original).**
**NO compartir variables de entorno ni config con Note9.**

## Diferencias con Note9 (original)

| Aspecto           | Note9 (original)          | VIVO V2058 (clon)         |
|-------------------|---------------------------|---------------------------|
| Dispositivo       | SM-N9600 (Samsung)        | V2058 (VIVO)              |
| Android           | 10                        | 13                        |
| Resolucion        | 720x1480 (override)       | 1080x2408 (nativa)        |
| Conectividad ADB  | WiFi TCP (127.0.0.1:5555) | USB directo               |
| Variables entorno | `TIKTOK_ADB_SERIAL=127.0.0.1:5555` | serial USB (detectado automaticamente) |
| TikTok pkg        | `com.zhiliaoapp.musically` | `com.zhiliaoapp.musically` (igual) |

## Archivos del clon

- `vivo/bootstrap_vivo.sh` — instalacion completa en VIVO desde cero
- `vivo/sync_to_vivo.sh` — sincronizacion desde PC al VIVO
- `vivo/diagnostico_vivo.sh` — diagnostico de salud del clon
- `vivo/SETUP.md` — documentacion detallada de instalacion
- `vivo/termux/deploy.sh` — deploy dentro de Termux (sdcard → home)
- `vivo/termux/vigia_vivo.sh` — loop 720s para VIVO
- `vivo/termux/widget_vivo.sh` — widget Termux para VIVO

## Coordenadas VIVO (1080x2408)

Las coordenadas base en `tiktok_evacuador_720.py` estan diseñadas para 720x1480
y se escalan via `tap_scaled()`. En VIVO 1080x2408, los factores son:
- x_scale = 1080/720 = 1.5
- y_scale = 2408/1480 ≈ 1.627

Si las coordenadas no calzan en VIVO, ajustar en `vivo/termux/deploy.sh`
exportando `TIKTOK_BASE_WIDTH` y `TIKTOK_BASE_HEIGHT` con valores nativos del VIVO.
