# Plan de Migración de Código y Solución de Red en Dispositivo "Vivo" (Termux)

El objetivo de este plan es enviar el código limpio y refactorizado de Linux hacia el dispositivo Vivo (Android/Termux), asegurando su autonomía total e investigando la dependencia a la red WiFi.

## User Review Required
Ninguna revisión bloqueante por el momento. Avanzaré con la exploración y te enviaré reportes si la configuración de red en Termux presenta bloqueos.

## Proposed Changes

### 1. Diagnóstico de Red (El problema del WiFi)
- **Investigación:** Analizar si hay direcciones IP estáticas locales (`192.168.x.x`) forzadas en los scripts de ambiente de Termux, en `resolv.conf` o si los webhooks apuntaban a localhost estático en lugar de utilizar rutas relativas o variables de entorno.
- **Corrección:** Volver toda configuración de red agnóstica o dinámica para que no "reviente" al cambiar de router o dirección DHCP.

### 2. Sincronización del Código Base (`agentes/`)
- Utilizar `adb push` para enviar diferencialmente la carpeta `youtube_uploader/` y `meta_uploader/` al almacenamiento en Termux del celular (`/data/data/com.termux/files/home/agentes/` o almacenamiento compartido).
- Asegurarnos que `quota_status.json` y el esquema multi-llave esté presente.

### 3. Recreación de la Arquitectura de Carpetas
- Crear en el dispositivo Vivo un árbol de directorios análogo al del PC (por ejemplo, `teasers_pendientes`, `videos subidos exitosamente`, `crudos_pendientes`) en un directorio de fácil acceso como `/sdcard/Antigravity/`.
- Ajustar `config.json` en Termux para que el código lea y mueva archivos mapeados exactamente hacia esas carpetas del almacenamiento interno.


### 5. Optimización de Escala (480 DPI) y Limpieza Profunda
- **Problema:** La interfaz sigue siendo pequeña incluso a 240/96 DPI. Existen procesos "zombies" de X11 y scrcpy que generan advertencias.
- **Cambio:** 
  - Subir la densidad a **480 DPI** (Escalado Master) para forzar que los íconos y el texto sean masivos y legibles como una "computadora de escritorio".
  - Implementar una subrutina de **Limpieza Total** (`pkill -9` en ambos dispositivos) antes de cada arranque para evitar errores de socket ocupado o instancias fantasmas.
  - Asegurar la sincronización de `wm density 480` en el display virtual del S24.
- **Persistencia:** Actualizar widgets y respaldos en el PC Desktop.

## Verification Plan
### Automated Tests
- Ejecutar `adb -s RFCX91HV4GD shell "ping -c 1 8.8.8.8"` para validar red del S24.
- Validar existencia de estructura `config.json` en ambos dispositivos.
### Manual Verification
- Pediré al usuario que pruebe dejando caer un archivo MP4 de prueba en la nueva carpeta `/sdcard/Antigravity...` de su S24 Ultra.
