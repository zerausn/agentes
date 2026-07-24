# AGENTS.md — TikTok Uploader VIVO (Clon)

**IMPORTANTE: Este es un CLON independiente para VIVO V2058.**
**NO modificar la instalacion del Note9 (original).**
**NO compartir variables de entorno ni config con Note9.**
**El widget `widget_vivo.sh` SOLO se despliega en VIVO via `sync_to_vivo.sh`.**
**El Note9 jamas recibe este archivo.**

## Diferencias con Note9 (original)

| Aspecto           | Note9 (original)          | VIVO V2058 (clon)         |
|-------------------|---------------------------|---------------------------|
| Dispositivo       | SM-N9600 (Samsung)        | V2058 (VIVO)              |
| Android           | 10                        | 13                        |
| Resolucion        | 720x1480 (override)       | 1080x2408 (nativa)        |
| UI Backend        | `accessibility`           | `adb`                     |
| ADB               | WiFi TCP (127.0.0.1:5555) | Local (127.0.0.1:5555)    |
| Widget wrapper    | `termux_widgets/6_SUBIR_TIKTOK720.sh` | `vivo/termux/widget_vivo.sh` |
| Vigia compartido  | `scripts/linux/vigia_tiktok720_termux.sh` | mismo (compartido) |
| Python script     | `tiktok_uploader/tiktok_evacuador_720.py` | mismo (compartido, pero usa ADB backend) |

## Arquitectura VIVO (actual)

El widget VIVO (`widget_vivo.sh`) es un wrapper DELGADO que llama al
vigía compartido `scripts/linux/vigia_tiktok720_termux.sh` con
`TIKTOK_UI_BACKEND=adb`. Asi:

1. Usuario toca widget `6_SUBIR_TIKTOK720` en pantalla inicio
2. `~/.shortcuts/6_SUBIR_TIKTOK720.sh` (copia de `widget_vivo.sh`)
   → ejecuta `vigia_tiktok720_termux.sh`
3. El vigía corre un bucle de 720s con `termux-wake-lock`
4. Cada ciclo llama a `tiktok_evacuador_720.py --open-next`
5. El Python usa `TIKTOK_UI_BACKEND=adb` → todos los comandos
   van via `adb -s 127.0.0.1:5555 shell` (shell UID)
6. Share intent via `am start` con flags correctos
7. Tiempo de settle dinámico: 120s (≤200MB) o 300s (>200MB)
8. Regreso a HOME en 20s tras publicar

### ¿Por que ADB en VIVO y no en Note9?
- En VIVO Android 13, `am start` / `input tap` requieren shell UID,
  no disponibles desde Termux. ADB local (`adb shell`) provee ese UID.
- En Note9 Android 10, `am broadcast` funciona directamente desde
  Termux, asi que usa `accessibility` backend sin ADB.

### Archivos que SOLO afectan al VIVO
- `vivo/termux/widget_vivo.sh` — widget wrapper (desplegado como `6_SUBIR_TIKTOK720.sh`)
- `vivo/sync_to_vivo.sh` — sincronizacion desde PC
- `vivo/diagnostico_vivo.sh` — diagnostico

### Archivos COMPARTIDOS (ambos dispositivos)
- `tiktok_uploader/tiktok_evacuador_720.py` — logica principal
- `scripts/linux/vigia_tiktok720_termux.sh` — loop 720s

## Comportamiento post-publicacion (VIVO)

Tras tocar "Publicar":

| Peso archivo | Settle | Descripcion                          |
|-------------|--------|--------------------------------------|
| ≤ 200MB     | 120s   | TikTok procesa rapido                |
| > 200MB     | 300s   | TikTok necesita mas tiempo           |

Luego del settle:
- 20s de espera
- `input keyevent KEYCODE_HOME` → escritorio
- Siguiente ciclo en 720s (manejado por el vigía)

## Coordenadas VIVO (1080x2408)

Las coordenadas base en `tiktok_evacuador_720.py` estan diseñadas para 720x1480
y se escalan via `tap_scaled()`. En VIVO 1080x2408, los factores son:
- x_scale = 1080/720 = 1.5
- y_scale = 2408/1480 ≈ 1.627
