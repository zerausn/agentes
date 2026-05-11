# Wireless Samsung DeX en Note 9 (Android 10)

Este documento detalla el procedimiento para habilitar Samsung DeX de forma inalámbrica en un Samsung Galaxy Note 9 y visualizarlo en una PC con Linux/Parrot OS utilizando `scrcpy`.

## Requisitos
- Samsung Galaxy Note 9 con Android 10.
- PC con Linux y `adb` / `scrcpy` instalados.
- Ambos dispositivos en la misma red WiFi.

## Paso 1: Activación de ADB por WiFi
Dado que Android 10 no soporta el emparejamiento nativo (Wireless Pairing), se debe usar el método de activación por USB:

1. Conectar el Note 9 a la PC mediante cable USB.
2. Habilitar el modo TCP/IP:
   ```bash
   adb tcpip 5555
   ```
3. Obtener la IP del Note 9 (Ajustes > Estado > Dirección IP).
4. Conectar por red:
   ```bash
   adb connect <IP_DEL_NOTE_9>:5555
   ```
5. Ya se puede desconectar el cable USB.

## Paso 2: El Truco del "Monitor Fantasma" (Virtual Display)
Para engañar al Note 9 y que crea que está conectado a un monitor HDMI (activando así DeX), forzamos una pantalla secundaria virtual:

```bash
adb shell settings put global force_desktop_mode_on_external_displays 1
adb shell settings put global enable_freeform_support 1
adb shell settings put global overlay_display_devices "1920x1080/160"
```

## Paso 3: Identificación del Display
Al crear la pantalla virtual, se genera un nuevo ID de display. Para encontrarlo:
```bash
scrcpy --list-displays
```
Normalmente aparecerá como `--display-id=6` (o similar).

## Paso 4: Lanzamiento de scrcpy
Para visualizar el escritorio DeX en pantalla completa y sin problemas de audio en Linux:
```bash
scrcpy -s <IP_DEL_NOTE_9>:5555 --display-id=6 --no-audio -f
```

## Scripts de Automatización
En este directorio se incluyen:
- `setup_wireless_dex.sh`: Realiza la configuración de red y pantalla virtual.
- `launch_scrcpy_dex.sh`: Conecta y lanza scrcpy automáticamente.
