# Tareas de Migración al Dispositivo Vivo (Termux)

- [x] Fase 1: Troubleshooting de Red (WiFi)
    - [x] Identificar dispositivo a través de `adb`.
    - [x] Buscar y purgar IPs estáticas quemadas en `config.json` o subrutinas.
    - [x] Revisar resolución DNS de Termux (`resolv.conf` y conectividad cruda).
- [x] Fase 2: Sincronización del Código de Subida (Linux -> Vivo)
    - [x] Enviar base `youtube_uploader` con las mejoras anti-loops y asíncronas vía `adb push`.
    - [x] Enviar base `meta_uploader` actualizada.
    - [x] Validar entornos y persistencias en `/data/data/com.termux/files/home`.
- [x] Fase 3: Ecosistema Local de Archivos Autónomos
    - [x] Generar `/sdcard/Antigravity/` y sus sub-rutas en Android:
        1. `crudos_pendientes` (Entrada a YT)
        2. `teasers_pendientes` (Entrada a FB/Meta)
        3. `videos subidos exitosamente` (Salida Exitosa de YT a FB)
        4. `subidos a facebbok` (Salida Ejecutada)
    - [x] Mapear el código condicionalmente (`if os.environ.get('PREFIX') == '/data/data/com.termux...'`) o en `config.json` para enrutar según la arquitectura (ARM64 vs x86).
- [x] Fase 4: Replicación en Samsung S24 Ultra
    - [x] Crear estructura de 4 carpetas en `/sdcard/Antigravity/`.
    - [x] Sideload de código optimizado ARM64.
    - [x] Activación remota de Widgets vía Termux Intent API (Broadcast).
    - [x] Aplicación de parche DNS (8.8.8.8) remoto.
- [x] Fase 5: Conectividad Tablet (Nativa)
    - [x] Identificar Tablet `SM-X210` (Tab A9+) e incapacidad de DP-In.
    - [x] Instalar dependencias base en Termux de la Tablet (`pkg`, `termux-x11-nightly`, `scrcpy`, `adb`).
    - [x] Inyectar llave ADB del PC en la Tablet para bypass de autorización ADB hacia S24 Ultra.
    - [x] Ajustar resolución Scrcpy para Tab A9+ (`1920x1200`), pantalla completa y WakeLock persistente.
    - [x] Crear widget `LANZAR_DEX.sh` en Termux de la Tablet.
- [ ] Fase 7: Troubleshooting de Rama Gemini (v9.5+)
    - [x] Identificar fallo de descubrimiento de puerto en `LANZAR_DEX_GEMINI`.
    - [/] Unificar lógica de descubrimiento con la versión v5.0 (Working).
    - [ ] Probar estabilidad de H.265 en ARM64.
- [x] Documentar resultados en `walkthrough.md`.
