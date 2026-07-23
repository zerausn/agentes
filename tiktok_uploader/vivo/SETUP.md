# SETUP VIVO V2058 — Clon TikTok Uploader

**Repositorio:** `zerausn/agentes` — Rama: `linux-arm64`
**Dispositivo:** VIVO V2058 (Android 13, 1080x2408)
**Original:** Note9 SM-N9600 (Android 10, 720x1480 override) — **NO MODIFICAR**

---

## Requisitos

- VIVO V2058 con:
  - USB Debugging habilitado (Developer Options)
  - Termux + Termux:Widget instalados
  - `android-tools` instalado en Termux (para ADB local)
- PC conectada al VIVO via USB-C

## Instalacion desde cero

### 1. En el VIVO — Preparar Termux

```bash
# Dentro de Termux en el VIVO:
pkg update && pkg upgrade -y
pkg install python android-tools termux-api -y
pkg install git -y  # opcional
```

Crear estructura de directorios en /sdcard:
```bash
mkdir -p /sdcard/Antigravity/{.state,subidos\ a\ facebbok,subidos\ a\ tiktok,widget_logs}
mkdir -p /data/data/com.termux/files/home/agentes/tiktok_uploader
```

### 2. En la PC — Clonar el repo

```bash
git clone -b linux-arm64 https://github.com/zerausn/agentes.git
cd agentes/tiktok_uploader/vivo
```

### 3. En la PC — Sincronizar al VIVO

```bash
# Opcion A: Usar el sync script (recomendado)
bash sync_to_vivo.sh

# Opcion B: Push manual
adb push tiktok_evacuador_720.py /sdcard/Antigravity/agentes/tiktok_uploader/
adb push termux/deploy.sh /sdcard/Antigravity/agentes/tiktok_uploader/termux/
adb push termux/vigia_vivo.sh /sdcard/Antigravity/scripts/linux/
```

Luego dentro de Termux en el VIVO:
```bash
bash /sdcard/Antigravity/agentes/tiktok_uploader/termux/deploy.sh
```

### 4. Probar

```bash
adb -s 34237840310037S shell run-as com.termux /data/data/com.termux/files/usr/bin/bash -c \
  'export TMPDIR=/data/data/com.termux/files/usr/tmp \
   export PATH=/data/data/com.termux/files/usr/bin:/system/bin:/system/xbin \
   export AGENTES_STORAGE_ROOT=/sdcard/Antigravity \
   export TIKTOK_UI_BACKEND=adb \
   export TIKTOK_ADB_SERIAL=34237840310037S \
   export TIKTOK_SHARE_METHOD=intent \
   export TIKTOK_PUBLISH_MODE=direct \
   export TIKTOK_POST_SETTLE_SECONDS=30 \
   python /data/data/com.termux/files/home/agentes/tiktok_uploader/tiktok_evacuador_720.py --open-next --dry-run'
```

### 5. Activar vigia automatico

Copiar widget Termux:
```bash
adb push termux/widget_vivo.sh /sdcard/Antigravity/termux_widgets/6_SUBIR_TIKTOK720.sh
```

Desde Termux en el VIVO, ejecutar el widget o:
```bash
bash /data/data/com.termux/files/home/agentes/scripts/linux/vigia_vivo.sh
```

---

## Coordenadas de pantalla

El script `tiktok_evacuador_720.py` usa `tap_scaled()` con base 720x1480.
En VIVO 1080x2408 se escala automaticamente.

**Si las coordenadas no calzan**, exportar antes de ejecutar:
```bash
export TIKTOK_BASE_WIDTH=1080
export TIKTOK_BASE_HEIGHT=2408
```

Para diagnosticar, usar `diagnostico_vivo.sh` que prueba cada coordenada.

---

## Mantenimiento

Actualizar el clon desde PC:
```bash
bash sync_to_vivo.sh
```

Verificar estado:
```bash
bash diagnostico_vivo.sh
```

## ADVERTENCIA

**Este clon es ESTRICTAMENTE para VIVO V2058.**
**No ejecutar estos scripts en el Note9.**
**No usar las variables de entorno del Note9 en el VIVO.**
**Los secretos/tokens de cada dispositivo son independientes.**
