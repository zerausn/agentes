# TikTok Uploader — Progress

## Goal
Publicar videos en TikTok via Content Posting API y configurar cuenta creador con monetización, incluyendo registro y aprobación de la app Uploaderbot en TikTok Developers.

## Status: APP REVIEW ATTEMPT #3 — SANDBOX VERIFICATION

### 2026-07-20 — Widget movil TikTok sin API

- Creado `tiktok_evacuador_720.py` para tomar 1 video desde `/sdcard/Antigravity/subidos a facebbok`.
- Creado widget `6_SUBIR_TIKTOK720.sh` con loop anti-Doze de 720s, siguiendo la logica de YouTube/Facebook.
- La UI de TikTok se controla por ADB local (`127.0.0.1:5555`) porque `input tap` desde Termux/Proot falla por `INJECT_EVENTS`.
- Caption alineado con YouTube/Facebook: nombre con `_`, `#PW`, `#teaser #N` solo para teasers, `Instagram Facebook Youtube`, linktree y hashtags `#teatro #performance #escriturasperformaticas`.
- Prueba real en Note9: 1 video llego al final del flujo y fue movido a `/sdcard/Antigravity/subidos a tiktok`.
- Documentacion operativa: `docs/TIKTOK_WIDGET720_NO_API.md`.
- Validacion adicional: se corrigio el texto exacto de TikTok a una sola linea con `Instagram Facebook Youtube`, sin `#cali`; `#teaser #N` queda condicionado al sufijo `_teaser_N`. Tambien se agrego confirmacion final de salida de UI antes de mover archivos.
- Prueba final del guard: `20251018 200806_teaser_3.mp4` publico con caption corregido, confirmo `foreground=com.sec.android.app.launcher` y se movio a `subidos a tiktok`.

### What's Working
- Flask app con OAuth PKCE (S256 code_challenge + code_verifier)
- Login Kit funcional con sandbox (scopes: user.info.basic, profile, stats, video.list)
- Dynamic redirect URI desde request.headers (via ProxyFix + X-Forwarded-*)
- Terms of Service y Privacy Policy servidos en el mismo dominio ngrok
- 3 TikTok verify files servidos en `/` y `/terms/`
- ngrok estable en Note9, URL fija: `https://gravy-diaper-refrain.ngrok-free.dev`
- ADB como canal de gestión (SSH cayó por cambio de IP, ADB via USB)
- Dual credential routing simplificado: siempre sandbox hasta aprobación

### Infrastructure
- **Host**: Note9 (SM-N9600) via Termux + proot-distro (Debian)
- **Web**: Flask (debug mode, auto-reload on file change)
- **Tunnel**: ngrok free, URL fija con authtoken persistente
- **Gestión**: ADB via USB (run-as com.termux)
- **Scripts**: `Iniciar_TikTok.sh` widget, `start_flask.sh` startup
- **Repo**: `agentes/` rama `linux-arm64` en GitHub

### OAuth Flow
1. `/login` genera PKCE pair + state CSRF + redirect a TikTok authorize
2. TikTok auth → callback → token exchange con code_verifier
3. `/upload` muestra página de subida (sandbox notice, Content Posting no disponible)
4. Scopes solicitados: user.info.basic, user.info.profile, user.info.stats, video.list

### TikTok Developer Portal Config
- Sandbox app: `performaticmachine` (client_key: `sbawgooshw60ceibf2`)
- Production app: `Uploaderbot` (client_key: `awhfxd65i4i468x8`) — pendiente de aprobación
- Redirect URIs registrados:
  - `https://gravy-diaper-refrain.ngrok-free.dev/callback`
  - `https://zerausn.github.io/agentes/callback.html`

## Next Steps (immediate)
1. Completar verify de URL prefix en portal TikTok (3 archivos)
2. Llenar review description y enviar a revisión
3. Tras aprobación: cambiar `_creds()` a production y probar Content Posting API

## Blockers
- **Sandbox no soporta Content Posting API** — solo Login Kit
- **Production app requiere aprobación** para usar video.upload/video.publish
- **Note9 IP dinámica** — SSH cayó al cambiar de red (10.100.x.x vs 192.168.1.x)
