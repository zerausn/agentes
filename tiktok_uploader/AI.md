# TikTok Uploader — AI Instructions

Subproyecto de publicación de videos en TikTok via Content Posting API.

## Antes de editar
- Lee `AGENTS.md` en la raiz del repo.
- Lee `AI.md` en la raiz del repo.
- Revisa `docs/` local para estado y decisiones.

## Stack
- Flask 3.x con ProxyFix
- TikTok Content Posting API v2
- Ngrok tunnel para exposicion 24/7 desde Note9 (Termux + Debian)
- GitHub Pages para website estático
- localhost.run como fallback para desarrollo local

## Reglas
- No subir CLIENT_SECRET ni tokens a git.
- No cambiar redirect URI dinámica sin registrar motivo.
- Si el tunel cambia, actualizar Redirect URI en portal TikTok.
- Cualquier cambio en scopes debe reflejarse en review description y website.

## Mapas
- `app.py` — rutas Flask, lógica OAuth y publicación
- `config.py` — credenciales y URLs desde env vars
- `docs/ARCHITECTURE.md` — diseño del sistema
- `docs/DECISIONS.md` — decisiones registradas
- `docs/PROGRESS.md` — estado actual

## Infraestructura
- **Servidor Flask**: Corre en Note9 (SM-X210, Termux + Debian) o localmente en Parrot OS.
- **Túnel principal**: Ngrok con authtoken, URL fija `gravy-diaper-refrain.ngrok-free.dev` (o la que asigne ngrok).
- **Túnel fallback**: localhost.run (SSH reverse, URL random cada vez).
- **Sitio estático**: GitHub Pages `zerausn.github.io/agentes/`.
- **Note9**: Flask + ngrok en tmux para operación 24/7 desatendida.

## Estado actual (2026-06-18)
- App review rechazada x2. Pendiente: arreglar login entry point, confirmar app icon, mejorar review description.
- Note9 necesita ngrok instalado para tunnel permanente.
- Redirect URI en portal TikTok debe coincidir con ngrok URL.
