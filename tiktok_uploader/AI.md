# TikTok Uploader — AI Instructions

Subproyecto de publicación de videos en TikTok via Content Posting API.

## Antes de editar
- Lee `AGENTS.md` en la raiz del repo.
- Lee `AI.md` en la raiz del repo.
- Revisa `docs/` local para estado y decisiones.

## Stack
- Flask 3.x con ProxyFix
- TikTok Content Posting API v2
- localhost.run tunnel (SSH reverse)
- GitHub Pages para website estático

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
