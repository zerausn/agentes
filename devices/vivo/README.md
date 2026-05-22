# Vivo V2058 — Perfil de Dispositivo

**Modelo:** V2058
**Android:** 13
**ABI:** arm64-v8a
**Usuario Termux:** u0_a289
**Serial ADB:** 34237840310037S
**Rol:** Sincronizador YouTube → Facebook

## Conexión

ADB WiFi inestable en red Univalle; se recomienda USB ADB Forward:

```bash
adb -s 34237840310037S forward tcp:38022 tcp:8022
ssh -p 38022 u0_a289@127.0.0.1
```

## Carpetas en el dispositivo

| Ruta | Contenido |
|------|-----------|
| `/sdcard/Antigravity/crudos_pendientes/` | Videos sin procesar |
| `/sdcard/Antigravity/teasers_pendientes/` | Teasers generados |
| `/sdcard/Antigravity/subidos_a_facebook/` | Videos ya subidos a FB |
| `/sdcard/Antigravity/videos_subidos_exitosamente/` | Videos subidos a YT |
| `/data/data/com.termux/files/home/agentes/` | Código del repo |

## Widgets instalados

Ver `termux_widgets/` en el repo.
