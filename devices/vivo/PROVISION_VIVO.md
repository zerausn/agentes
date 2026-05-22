# Aprovisionamiento Completo del Vivo V2058

## 1. Copiar widgets al dispositivo

```bash
# Desde el host (Linux/Parrot):
cd /home/zerausn/Documents/Antigravity/agentes

# Empaquetar widgets
mkdir -p /tmp/codex_termux_widgets
cp termux_widgets/*.sh /tmp/codex_termux_widgets/
cp termux_widgets/install_shortcuts.sh /tmp/codex_termux_widgets/

# Subir al Vivo
adb -s 34237840310037S push /tmp/codex_termux_widgets /sdcard/Download/

# Instalar en Termux
adb -s 34237840310037S shell run-as com.termux bash /sdcard/Download/codex_termux_widgets/install_shortcuts.sh
```

## 2. Copiar carpetas de datos al Vivo

```bash
# crudos_pendientes (30 GB)
adb -s 34237840310037S push /ruta/origen/crudos_pendientes/ /sdcard/Antigravity/crudos_pendientes/

# teasers_pendientes (10 GB)
adb -s 34237840310037S push /ruta/origen/teasers_pendientes/ /sdcard/Antigravity/teasers_pendientes/

# subidos a facebook (11 GB)
adb -s 34237840310037S push /ruta/origen/subidos_a_facebook/ /sdcard/Antigravity/subidos_a_facebook/

# agentes (134 MB) - código
adb -s 34237840310037S push /ruta/origen/agentes/ /sdcard/Antigravity/agentes/

# videos subidos exitosamente (vacío)
adb -s 34237840310037S shell mkdir -p /sdcard/Antigravity/videos_subidos_exitosamente
```

> Nota: reemplaza `/ruta/origen/` por la ruta real en el PC/Note9/S24
> donde residen los datos actualmente.

## 3. Dependencias

```bash
# En Termux:
pkg install -y python3 ffmpeg git openssh proot-distro termux-api
pip3 install google-auth-oauthlib google-api-python-client httplib2

# En Debian (proot):
proot-distro install debian
proot-distro login debian
  apt update && apt install -y python3 python3-pip ffmpeg
  pip3 install yt-dlp google-auth-oauthlib google-api-python-client httplib2 requests python-dotenv
```

## 4. Bootstrap

```bash
# Dentro de Termux:
cd ~/agentes
bash scripts/linux/bootstrap_termux_arm64.sh vivo
```

## 5. Verificación

```bash
# Widgets instalados
ls -la ~/.shortcuts/

# SSH funcionando
ssh -p 38022 u0_a289@127.0.0.1 whoami

# Python y ffmpeg
proot-distro login debian -- python3 --version
proot-distro login debian -- ffmpeg -version

# Pipeline
ls -la /sdcard/Antigravity/
```
