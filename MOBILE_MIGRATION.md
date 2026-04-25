# Guía de Migración de Agentes a Dispositivos Móviles (Termux/Debian)

Esta guía documenta la migración exitosa de la infraestructura de agentes de transcodificación de video 4K a un dispositivo Android (Vivo) usando Termux y proot-distro (Debian 13).

## 🚀 Arquitectura General
El sistema opera dentro de un entorno **CRUTA (Chroot/PRoot)** para mantener la compatibilidad con binarios de Linux (FFmpeg, Python, Node.js) sin necesidad de acceso Root en el teléfono.

- **Host**: Android (Termux)
- **Container**: Debian 13 (proot-distro)
- **Red**: Puerto SSH 8022 (Termux)
- **Almacenamiento**: Carpeta `~/agentes` sincronizada con el PC.

## 🛠️ Configuraciones Realizadas

### 1. Entorno de Dependencias (Debian)
Para que el sincronizador de YouTube a Facebook funcione en 4K, se instalaron los siguientes componentes dentro de Debian:
- **Python 3.13**: Base de ejecución de los agentes.
- **FFmpeg 7.x**: Para la transcodificación de 320MB MKV a MP4 compatibles en 2 pasos.
- **Node.js v20**: Esencial para que `yt-dlp` resuelva el "n challenge" de YouTube y evite errores 403 Forbidden.

### 2. Parches de Rutas y Portabilidad
Se adaptó el código de `youtube_to_fb_watcher.py` para eliminar dependencias de hardware del PC:
- **Cookies**: Se inyectaron `cookies.txt` en formato Netscape para evitar la dependencia de perfiles de Microsoft Edge.
- **Downloads**: Se redirigió la salida a `/data/data/com.termux/files/home/agentes/youtube_uploader/downloads`.
- **Symlinks**: Se creó un vínculo simbólico a la carpeta pública del celular para ver los videos desde la Galería:
  `~/storage/downloads/Agentes_YouTube_4K` -> `~/agentes/youtube_uploader/downloads/`

### 3. Persistencia (Termux:Boot + Wakelock)
Para asegurar que los agentes no mueran cuando la pantalla se apague:
- Se instaló `termux-api` y se activó `termux-wake-lock`.
- Se configuró un script en `~/.termux/boot/start_sshd.sh` para iniciar el servicio SSH automáticamente al encender el teléfono.

### 4. Monitoreo Térmico
Se creó un widget personalizado en `~/.shortcuts/Monitorear_Temperaturas.sh` que reporta:
- Temperatura de la batería.
- Temperaturas de los núcleos de la CPU (vía `/sys/class/thermal/`).

## 🌳 Rama Git: `linux-arm64`
Todos los cambios específicos para Android/Termux están aislados en la rama **`linux-arm64`**.
- Utiliza la estrategia de descarga de **2 pasos** (Combined Download + Custom FFmpeg Transcode).
- Incluye el flag `--js-runtimes node` nativo.

## 🔧 Mantenimiento
- **Reiniciar Agentes**: Usar el botón de Termux:Widget en el escritorio del celular.
- **Ver Logs**: `tail -f ~/agentes/youtube_uploader/youtube_to_fb_sync.log`
- **Temperatura**: Usar el botón "Monitorear Temperaturas" para vigilar el calentamiento durante transcodificaciones 4K.
