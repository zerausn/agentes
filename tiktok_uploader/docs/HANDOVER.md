# TikTok Uploader — Handover

## Estado Actual (2026-07-21): PRODUCCIÓN CON UI AUTOMATION (BLOQUEADO PARA NOTE9)

El sistema está publicando videos reales en TikTok usando Share Intent + ADB local.
La Content Posting API no está aprobada; no hay plazo estimado.

> [!WARNING]
> **VERSIÓN BLOQUEADA PARA NOTE9 (SM-N9600, Android 10).**
> Este código está probado y funciona perfectamente en el Note9. Intentos pasados de adaptarlo o probarlo en el Samsung Galaxy S24 (Android 14) introdujeron errores y rompieron la estabilidad en el Note9. **Bajo ninguna circunstancia se debe modificar o "contaminar" este código funcional para intentar dar soporte al S24**, a menos que haya una petición explícita del usuario para revisar ese caso específico. Si funciona en el Note9, se queda así.

---

## Contexto Crítico

### Stack de Producción

| Componente | Detalle |
|---|---|
| Dispositivo | Samsung Note9 (SM-N9600) — nodo 24/7 |
| OS | Android 10, override display 720x1480 |
| Terminal | Termux + proot-distro (Debian arm64) |
| Automatización | Python 3.13 + ADB local |
| Loop | Widget Termux `6_SUBIR_TIKTOK720` (720s) |
| ADB | `127.0.0.1:5555` — local, sin WiFi |
| Origen | `/sdcard/Antigravity/subidos a facebbok` |
| Destino | `/sdcard/Antigravity/subidos a tiktok` |
| Logs | `/sdcard/Antigravity/widget_logs/6_SUBIR_TIKTOK720.log` |

### Método Activo
- **Share Intent** (`TIKTOK_SHARE_METHOD=intent`): `am start SEND` con `content://` URI desde MediaStore. Abre TikTok directamente en editor.
- **Modo**: `direct` (publica automáticamente) o `draft` (guarda borrador).
- **Confirmación**: `publish_confirmed()` asume éxito si dump UI está vacío (animación post-publicación).

### Subsistema Web Flask (EN PAUSA)
- No se usa para producción. Solo para cuando la API sea aprobada.
- Flask + ngrok en Note9, URL: `https://gravy-diaper-refrain.ngrok-free.dev`
- Tokens: Sandbox (`sbawgooshw60ceibf2`). Production (`awhfxd65i4i468x8`) pendiente.

---

## Cómo Acceder al Note9

### ADB via USB (cuando hay cable)
```bash
adb connect 192.168.0.100:5555    # reemplazar IP
adb shell
```

### ADB via USB → TCP (si se perdió conexión local)
```bash
adb shell "su -c 'setprop service.adb.tcp.port 5555 && stop adbd && start adbd'"
# O desde USB:
adb tcpip 5555
```

### ADB local (desde Termux en el Note9)
```bash
adb connect 127.0.0.1:5555
adb devices
# Debe mostrar: 127.0.0.1:5555    device
```

### Probar el evacuador manualmente (dry-run)
```bash
# Desde proot:
cd /root/agentes/tiktok_uploader
AGENTES_STORAGE_ROOT=/sdcard/Antigravity \
TIKTOK_UI_BACKEND=adb \
TIKTOK_ADB_SERIAL=127.0.0.1:5555 \
TIKTOK_PUBLISH_MODE=direct \
python3 tiktok_evacuador_720.py --dry-run --open-next

# Publicar real (sin dry-run):
AGENTES_STORAGE_ROOT=/sdcard/Antigravity \
TIKTOK_UI_BACKEND=adb \
TIKTOK_ADB_SERIAL=127.0.0.1:5555 \
TIKTOK_PUBLISH_MODE=direct \
python3 tiktok_evacuador_720.py --open-next
```

### Ver estado de la cola
```bash
python3 tiktok_evacuador_720.py --status
```

---

## Cómo Sincronizar Cambios desde PC al Note9

### Usando `sync_to_note9.sh`
```bash
# Desde Parrot:
bash /home/zerausn/Documents/Antigravity/agentes/tiktok_uploader/termux/sync_to_note9.sh <IP_DEL_NOTE9>
```

### Manualmente
```bash
# 1. Push a /sdcard/
adb push tiktok_evacuador_720.py /sdcard/Antigravity/agentes/tiktok_uploader/
adb push config.py /sdcard/Antigravity/agentes/tiktok_uploader/

# 2. Copiar a Termux home (usando run-as com.termux, NO SSH)
adb shell run-as com.termux /data/data/com.termux/files/usr/bin/bash -c \
  "cp -r /sdcard/Antigravity/agentes/tiktok_uploader/* /data/data/com.termux/files/home/agentes/tiktok_uploader/"

# 3. Copiar scripts
adb push vigia_tiktok720_termux.sh /sdcard/Antigravity/scripts/linux/
adb push _proot_bind.sh /sdcard/Antigravity/scripts/linux/
adb shell run-as com.termux /data/data/com.termux/files/usr/bin/bash -c \
  "cp /sdcard/Antigravity/scripts/linux/* /data/data/com.termux/files/home/agentes/scripts/linux/"
```

---

## Termux Widget y SELinux

Los shortcuts del widget DEBEN crearse desde `run-as com.termux`.
Nunca via scp/SSH — el contexto SELinux será incorrecto y el widget ignorará el archivo.

```bash
# Forma correcta (en el Note9 via ADB):
adb shell run-as com.termux /data/data/com.termux/files/usr/bin/bash -c "
  mkdir -p ~/.shortcuts
  cp /sdcard/Antigravity/termux_widgets/6_SUBIR_TIKTOK720.sh ~/.shortcuts/6_SUBIR_TIKTOK720.sh
  chmod +x ~/.shortcuts/6_SUBIR_TIKTOK720.sh
"
```

El widget corre como `u0_a291` (UID de `com.termux`). Los shortcuts deben tener ese contexto SELinux.

---

## Diagnóstico Rápido

```bash
# Ejecutar diagnóstico completo:
bash /sdcard/Antigravity/agentes/tiktok_uploader/termux/diagnostico_tiktok.sh

# Verificar ADB local:
adb devices | grep 127.0.0.1

# Verificar videos pendientes:
ls -lt /sdcard/Antigravity/subidos\ a\ facebbok/

# Ver logs:
tail -f /sdcard/Antigravity/widget_logs/6_SUBIR_TIKTOK720.log

# Ver historial:
cat /sdcard/Antigravity/.state/tiktok_queue.json | python3 -m json.tool
```

---

## Problemas Conocidos

### ADB local perdido
- **Síntoma**: El widget falla con error de conexión ADB.
- **Causa**: `adbd` dejó de escuchar en TCP (reinicio, Doze, etc.).
- **Solución**: Conectar USB y ejecutar `adb tcpip 5555`.

### uiautomator dump vacío
- **Síntoma**: `publish_confirmed()` retorna True inmediatamente porque dump está vacío.
- **Causa**: Animación post-publicación o TikTok en pantalla de transición.
- **Decisión**: Se asume éxito — no hay mejor método sin API.

### TikTok cambia layout
- **Síntoma**: Las coordenadas fijas no funcionan más.
- **Causa**: Actualización de TikTok mueve elementos UI.
- **Solución**: Revisar coordenadas con `uiautomator dump` y ajustar.

### Flujo de borrador no verificado post-publicación
- **Nota**: El modo draft guarda el video tocando "Borradores" pero no hay confirmación de que TikTok efectivamente lo guardó. Asumimos éxito si el botón fue tocado.

---

## Archivos Clave

| Archivo | Propósito |
|---|---|
| `tiktok_evacuador_720.py` | Script principal de evacuación (997 líneas) |
| `vigia_tiktok720_termux.sh` | Loop de vigilancia 720s |
| `_proot_bind.sh` | Bind mounts para proot |
| `deploy.sh` | Copia archivos desde /sdcard a Termux home |
| `diagnostico_tiktok.sh` | Diagnóstico completo del sistema |
| `sync_to_note9.sh` | Sincronización desde PC al Note9 |
| `tiktok_daemon.sh` | Daemon legacy Flask+ngrok (obsoleto) |
| `config.py` | Config API TikTok (sandbox/production) |
| `app.py` | Flask web app (en pausa) |

## Variables de Entorno Requeridas en el Widget

El widget `vigia_tiktok720_termux.sh` pasa estas variables al evacuador:
- `AGENTES_STORAGE_ROOT=/sdcard/Antigravity`
- `TIKTOK_UI_BACKEND=adb`
- `TIKTOK_ADB_SERIAL=127.0.0.1:5555`
- `TIKTOK_PUBLISH_MODE=direct` (configurable vía env `TIKTOK_PUBLISH_MODE`)

## Rama Git
- `linux-arm64` — todo el código de agentes
- Origin: `https://github.com/zerausn/agentes.git`
