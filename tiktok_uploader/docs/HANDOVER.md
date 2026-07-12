# TikTok Uploader — Handover

## Current State (2026-07-12)

App review attempt #3 — sandbox verification in progress.

## Critical Context

### Running Services
- **Flask**: Running on Note9 (10.100.24.236:8080) inside Debian proot
- **Tunnel**: `https://gravy-diaper-refrain.ngrok-free.dev` (ngrok, stable URL)
- **Gestión remota**: ADB via USB (SSH cayó por cambio de red)
- **Sandbox activo**: client_key `sbawgooshw60ceibf2`

### Acceso Note9
```bash
# ADB via USB
adb shell run-as com.termux /data/data/com.termux/files/usr/bin/bash -c "comandos"

# Para escribir archivos
adb push archivo /sdcard/archivo
adb shell run-as com.termux /data/data/com.termux/files/usr/bin/bash -c "cp /sdcard/archivo /data/data/com.termux/files/home/agentes/tiktok_uploader/"

# Iniciar Flask manual
adb shell run-as com.termux /data/data/com.termux/files/usr/bin/bash -c \
  'export PATH=/data/data/com.termux/files/usr/bin:$PATH; \
   setsid /data/data/com.termux/files/home/start_flask.sh &'
```

### En el Note9
- Flask runs en `/root/agentes/tiktok_uploader/` (bind mount desde Termux home)
- ngrok corre en proot con authtoken persistente
- Widget `Iniciar_TikTok.sh` en `~/.shortcuts/`
- Script `start_flask.sh` en home para reinicio manual
- **NO hay tmux** — procesos gestionados via setsid desde ADB

### Rama Git
- `linux-arm64` — código actual de tiktok_uploader
- Origin: `https://github.com/zerausn/agentes.git`

### Credenciales (TikTok Developers)
| App | client_key | Estado |
|-----|-----------|--------|
| performaticmachine (sandbox) | `sbawgooshw60ceibf2` | **Activo** |
| Uploaderbot (production) | `awhfxd65i4i468x8` | Pendiente de review |

### Verify files servidos
| Archivo | URL |
|---------|-----|
| `tiktokax8X4G179reOCBSgW2YLn7fvPMfom6Rz.txt` | `/terms/tiktokax8X4G179reOCBSgW2YLn7fvPMfom6Rz.txt` |
| `tiktok6CtmXXeaDFMo42fDZk4QgJTwB4VlmE9S.txt` | `/tiktok6CtmXXeaDFMo42fDZk4QgJTwB4VlmE9S.txt` |
| `tiktok0aF0EeTBpj5jZNKr0RJHRsKyfYuenG9i.txt` | `/tiktok0aF0EeTBpj5jZNKr0RJHRsKyfYuenG9i.txt` |

## Cómo sincronizar cambios desde Parrot al Note9

```bash
# 1. Editar archivos locales en /home/zerausn/Documents/Antigravity/agentes/tiktok_uploader/

# 2. Pushear a /sdcard/
adb push archivo /sdcard/archivo

# 3. Copiar a Termux home (run-as com.termux, NO com.termux.api)
adb shell run-as com.termux /data/data/com.termux/files/usr/bin/bash -c \
  "cp /sdcard/archivo /data/data/com.termux/files/home/agentes/tiktok_uploader/archivo"

# 4. Flask debug mode recarga automáticamente
# Si Flask cayó, reiniciar:
adb shell run-as com.termux /data/data/com.termux/files/usr/bin/bash -c \
  'export PATH=/data/data/com.termux/files/usr/bin:$PATH; \
   setsid /data/data/com.termux/files/home/start_flask.sh &'
```

## Termux Widget y SELinux

Los shortcuts del widget DEBEN crearse desde `run-as com.termux` para que tengan
el contexto SELinux correcto. Nunca via scp/SSH.

## Problemas conocidos
- Flask debug mode: se cae al recargar si el adb shell session termina abruptamente
- ngrok requiere `setsid` para sobrevivir al cierre de la shell ADB
- El `run-as com.termux.api` NO puede escribir en Termux data dir (SELinux), usar `run-as com.termux`
- Para escribir archivos, usar `/data/data/com.termux/files/usr/bin/bash` dentro de run-as (no el `/system/bin/sh` default)
