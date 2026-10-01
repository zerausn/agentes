# Captura 4K con Firefox y CDP Clásico

Este documento describe el flujo exacto utilizado en el PC (`linux`) para forzar la captura de UMP en resolución 2160p60 utilizando Firefox, `mitmproxy` y el protocolo CDP clásico (`/json`).

## Arquitectura del Pipeline

El proceso se compone de tres piezas principales trabajando en sincronía:

1. **`yt_capture.py` (Addon de mitmproxy):**
   - Escucha el tráfico en el puerto `8080`.
   - Intercepta todas las respuestas de `googlevideo.com` que contengan `application/vnd.yt-ump` o mime types de video/audio.
   - Guarda cada segmento en el disco físico (`/mnt/Videos/yt_browser_capture/segments/`).
   
2. **Firefox (Configurado con perfil CDP):**
   - Se lanza apuntando al proxy de `mitmproxy`.
   - Requiere obligatoriamente que el certificado SSL de `mitmproxy` esté instalado en la base de datos NSS de su perfil (`cert9.db`).
   - Se activa la preferencia `remote.active-protocols = 2` para exponer el endpoint CDP clásico en lugar de usar únicamente WebDriver BiDi.
   - Escucha en el puerto `9222`.

3. **`cdp_4k.py` (Driver CDP):**
   - Se conecta al endpoint `http://127.0.0.1:9222/json` para obtener el WebSocket Debugger URL de la pestaña de YouTube.
   - Espera a que el video alcance el estado `readyState >= 2`.
   - Lanza la reproducción vía `play()`.
   - Navega por el DOM del menú de configuración (`.ytp-settings-button`) para seleccionar manualmente la opción "2160p" o "Calidad".

4. **`yt_ump_extract.py` (Extractor final):**
   - Escanea todos los archivos `.ump` generados por el addon.
   - Extrae los boxes ISO BMFF (`ftyp`, `moov`, `moof`, `mdat`).
   - Reensambla desde el último bloque de inicialización válido para generar un `.mp4` completamente funcional en `/mnt/Videos/yt_browser_capture/salidas/`.

## Configuración Especial Requerida (Firefox)

Para que Firefox permita la instrumentación en versiones ESR recientes (como la 115 o la 128/140), el perfil `user.js` debe contener:

```javascript
user_pref("remote.active-protocols", 2); // Exponer /json (CDP clásico)
user_pref("network.proxy.type", 1);
user_pref("network.proxy.http", "127.0.0.1");
user_pref("network.proxy.http_port", 8080);
user_pref("network.proxy.ssl", "127.0.0.1");
user_pref("network.proxy.ssl_port", 8080);
user_pref("network.proxy.no_proxies_on", "localhost, 127.0.0.1"); // Fundamental para el driver CDP
user_pref("media.autoplay.default", 0);
user_pref("media.autoplay.blocking_policy", 0);
```

## Ejecución Manual

```bash
# 1. Iniciar mitmdump
~/venv-mitm/bin/mitmdump -s /mnt/Videos/yt_browser_capture/yt_capture.py \
    --listen-host 127.0.0.1 --listen-port 8080

# 2. Iniciar Firefox (Con DISPLAY real)
XAUTHORITY=~/.Xauthority DISPLAY=:0 firefox-esr \
  --profile /tmp/perfil_cdp \
  --remote-debugging-port=9222 \
  --remote-allow-origins='*' \
  --autoplay-policy=no-user-gesture-required \
  --no-remote \
  "https://www.youtube.com/watch?v=VIDEO_ID"

# 3. Lanzar CDP Driver (Cuando el video cargue)
~/venv-mitm/bin/python /mnt/Videos/yt_browser_capture/cdp_4k.py
```
