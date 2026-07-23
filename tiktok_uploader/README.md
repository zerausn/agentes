# TikTok Uploader Module

**DISPOSITIVOS SOPORTADOS:**
- **Note9 (SM-N9600, Android 10)** — ORIGINAL. Rama `main` / `linux-arm64`.
- **VIVO V2058 (Android 13)** — CLON independiente. Rama `linux-arm64`. Ver [`vivo/`](vivo/).

> [!WARNING]
> **NO mezclar configuraciones entre Note9 y VIVO.**
> Cada dispositivo tiene su propia config, coordenadas, y serial ADB.
> Los scripts en `vivo/` son exclusivos del VIVO.

---

Este módulo contiene una aplicación Flask que sirve como bot/agente de subida de videos a TikTok utilizando la API oficial de TikTok (v2). Permite automatizar la publicación de videos desde tu computadora local.

---

## 🏗️ Arquitectura y Flujo de Autenticación

Dado que TikTok requiere OAuth 2.0 para interactuar con la cuenta del usuario, la aplicación web expone dos modos de inicio de sesión:

1. **Login Completo (Full Scope):**
   - Solicita acceso a los scopes de publicación (`video.upload`, `video.publish`) junto con información básica (`user.info.basic`).
   - Requiere que la aplicación de TikTok Developers tenga aprobados estos permisos avanzados.
2. **OAuth Básico (Basic Scope):**
   - Solicita únicamente información básica (`user.info.basic`).
   - Sirve como método de prueba para verificar que la configuración de red, tokens, claves de cliente y la URI de redirección estén correctamente configurados en la consola de TikTok Developers.

---

## 📂 Estructura del Módulo

- **`app.py`**: Servidor Flask principal que implementa el flujo OAuth y la interfaz de subida.
- **`tiktok_evacuador_720.py`**: Evacuador movil sin API aprobada. Toma 1 video desde `/sdcard/Antigravity/subidos a facebbok`, lo comparte a la app TikTok y lo mueve a `subidos a tiktok` cuando termina el ciclo.
- **`config.py`**: Carga de configuración desde variables de entorno con valores predeterminados seguros.
- **`demo_script.py`**: Script de consola interactivo para ilustrar el flujo de peticiones OAuth y API a mano.
- **`run_flask.sh`**: Wrapper simple para ejecutar la app de Flask cargando variables desde `.env.local`.
- **`start_demo_stack.sh`**: Script maestro de inicialización. Levanta Flask en segundo plano, espera a que responda y luego inicia el túnel público.
- **`start_cloudflare_tunnel.sh`** / **`start_ngrok_tunnel.sh`**: Levantadores de túneles usando Cloudflare o Ngrok respectivamente.
- **`stop_demo_stack.sh`**: Detiene ordenadamente todos los procesos en segundo plano (túneles y Flask) usando archivos PID locales en `.run/`.

---

## 🔧 Configuración (`.env.local`)

El servidor busca un archivo `.env.local` en esta carpeta para cargar la configuración. Puedes copiarla desde `.env.example`:

```env
TIKTOK_CLIENT_KEY="tu_client_key"
TIKTOK_CLIENT_SECRET="tu_client_secret"
PUBLIC_BASE_URL="https://tu-tunel-publico.trycloudflare.com"
REDIRECT_URI="https://tu-tunel-publico.trycloudflare.com/callback"
TIKTOK_SCOPES="user.info.basic,video.upload,video.publish"
FLASK_SECRET_KEY="tu-llave-secreta-para-cookies"
PORT=8080
FLASK_DEBUG=true
```

> [!IMPORTANT]
> El túnel actualiza automáticamente la variable `PUBLIC_BASE_URL` y `REDIRECT_URI` en tu archivo `.env.local` cada vez que se inicia el stack si usas Cloudflare o Ngrok dinámico. No olvides actualizar este valor en la consola de TikTok Developers en la sección **Redirect URI**.

---

## 🚀 Cómo Iniciar el Stack Local

Dado que TikTok requiere HTTPS para las URIs de redirección de OAuth, debes exponer tu servidor local a internet. El stack lo automatiza por ti.

### Requisitos Previos

1. Asegúrate de tener instalado `cloudflared` (túneles Cloudflare) o `ngrok` en tu sistema.
2. Configura tus claves de cliente en tu consola de desarrollador de TikTok.

### 1. Iniciar con Túnel Cloudflare (Por defecto)
```bash
./start_demo_stack.sh
```
Esto levantará Flask en `http://127.0.0.1:8080` y abrirá un túnel dinámico de Cloudflare. Imprimirá en la terminal la URL pública asignada y la Redirect URI exacta que debes configurar.

### 2. Iniciar con Túnel Ngrok
```bash
TUNNEL_PROVIDER=ngrok ./start_demo_stack.sh
```

### 3. Detener el Stack Completo
```bash
./stop_demo_stack.sh
```
Este comando matará los procesos de Flask y del proveedor de túnel que quedaron corriendo en el fondo de manera segura.

---

## 📱 Widget móvil sin Content Posting API

Mientras la API oficial no este aprobada, el nodo Android puede usar el widget `6_SUBIR_TIKTOK720.sh`.
La guia operativa esta en [`docs/TIKTOK_WIDGET720_NO_API.md`](docs/TIKTOK_WIDGET720_NO_API.md).

---

## 🔄 Cambios 2026-07-20 — Compatibilidad Android 14 / Samsung Galaxy S24

### Problema detectado
Android 14 en el Galaxy S24 bloquea el intent `android.intent.action.SEND` con el error
`INTERACT_ACROSS_USERS_FULL`, impidiendo que el script abriera TikTok con el video precargado.

### Solución implementada en `tiktok_evacuador_720.py`

| Área | Cambio |
|---|---|
| **Apertura de TikTok** | Reemplazado `launch_share` / `launch_direct` / `launch_termux_open` por `launch_tiktok_home()` usando `monkey -p com.zhiliaoapp.musically`. |
| **Flujo de navegación** | Nuevo flujo: Tap **Crear (+)** → Tap **Cargar** → dropdown **Recientes** → selección de carpeta por UI → video → Siguiente. |
| **Selección de carpeta** | La función `automate_tiktok_publish_coords(caption, folder_name)` busca el nombre de la carpeta en la UI con `uiautomator dump` y hace tap dinámico (no coordenada fija). |
| **Botón Siguiente editor** | Coordenada corregida de `(665, 77)` a `(531, 1341)` por cambio de layout en S24. |
| **Cierre de teclado** | `close_caption_editor()` ahora toca el fondo de pantalla `(360, 400)` para quitar el foco del campo de texto, luego KEYCODE_BACK como respaldo. |
| **Dump de UI** | `dump_ui()` borra el XML anterior con `rm -f` antes de ejecutar `uiautomator dump`, evitando leer estados rancios durante animaciones. |
| **Confirmación de publicación** | `publish_confirmed()` asume éxito si `dump_ui()` devuelve lista vacía (TikTok animando transición al feed bloquea `uiautomator`). |
| **Orden de archivos** | Sincronización infalible mediante consulta nativa a **MediaStore**. Python ejecuta `adb shell content query` ordenando por `date_added DESC, _id DESC` (el mismo SQL exacto que usa la galería "Recientes" de TikTok). Se corrigió un bug de "quote-stripping" de subprocess para asegurar que la consulta de MediaStore devuelva el video correcto. |

### Widget Termux (`6_SUBIR_TIKTOK720.sh`)
- **Intervalo:** 720 segundos entre ciclos.
- **Fuente:** `/sdcard/Antigravity/subidos a facebbok/`
- **Destino exitoso:** `/sdcard/Antigravity/subidos a tiktok/`
- **Log:** `/sdcard/Antigravity/widget_logs/6_SUBIR_TIKTOK720.log`
- **Wake lock:** activado automáticamente para evitar que Doze suspenda el proceso.

---

## 🔒 2026-07-21 — Fixes y Bloqueo de Versión para Note9 (Android 10)

> [!WARNING]
> **ESTE CÓDIGO ESTÁ OPTIMIZADO Y CONFIRMADO COMO FUNCIONAL EN EL NOTE9 (SM-N9600, Android 10).**
> Anteriormente, intentos de hacer que el código funcionara en el S24 (Android 14) introdujeron bugs y comportamientos inestables. **Bajo ninguna circunstancia se debe contaminar o modificar este código funcional del Note9** para intentar solucionar problemas en el S24, a menos que el usuario lo solicite de manera explícita. El código actual debe mantenerse así.

### Bugs Críticos Resueltos en Note9:

| Área | Solución Implementada |
|---|---|
| **Caché Rancio UI** | **Bug Crítico**: `dump_ui()` reutilizaba el XML anterior si `_uiautomator_available` era True. Esto hacía que Python viera una captura "congelada" del pasado y no la pantalla actual. **Fix**: Se borra `tiktok_ui.xml` con `rm -f` obligatoriamente en cada llamada. |
| **Share Intent** | Vuelto al método `TIKTOK_SHARE_METHOD=intent` como el predeterminado para el Note9 (más estable que `monkey`). `vigia_tiktok720_termux.sh` ahora declara explícitamente `AGENTES_STORAGE_ROOT`, `TIKTOK_SHARE_METHOD=intent`, y `TIKTOK_PUBLISH_MODE=direct`. |
| **Detección Editor** | El flujo intent ahora intenta hacer tap en "Siguiente" hasta 2 veces usando detección de UI y fallback por coordenadas, ya que hay versiones de TikTok con 1 o 2 pantallas de editor. |
| **Verificación Publicar** | El script ahora detecta el botón Publicar usando UI y usa la coordenada `(608, 80)` solo como fallback. La variable `publish_ok` ahora refleja estrictamente el resultado de la función `publish_confirmed()`, en lugar de asumir éxito ciegamente. |
| **Publicaciones Duplicadas** | **Bug**: El script publicaba el mismo video hasta 11 veces. **Causa**: La validación post-publicación incluía la palabra `crear`. Tras publicar, TikTok vuelve al Home Feed, cuyo botón inferior dice "Crear (+)". El script creía erróneamente que seguía en el editor y marcaba la publicación como fallida. **Fix**: Se eliminó `crear` de las variables `POST_RE` y `PUBLICAR_RE`. |
| **Almacenamiento Lleno** | **Bug**: El dispositivo se quedó con 0 bytes libres por culpa de la opción "Guardar en el dispositivo" de TikTok, que guardaba en `/sdcard/DCIM/Camera` copias pesadas de todo lo publicado. **Fix**: El usuario debe apagar manualmente este interruptor en TikTok (la preferencia persiste para el bot). Se eliminaron copias redundantes. |
