# TikTok Uploader Module

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
