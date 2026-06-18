# TikTok Uploader — Key Decisions

## 2026-05-26: OAuth login via 302 redirect instead of JS redirect
- Context: Cloudflare proxy was corrupting JavaScript-based redirects in the tunnel.
- Decision: Use Flask `redirect()` (HTTP 302) for `/login` endpoint instead of client-side JS redirect.
- Consequence: Cleaner OAuth flow, no Cloudflare corruption.

## 2026-05-26: localhost.run over trapdoor.sh as primary tunnel
- Context: trapdoor.sh was returning persistent 429 (rate limit) and 502 (bad gateway) errors.
- Decision: Fall back to localhost.run (SSH reverse tunnel) which is free and reliable.
- Consequence: Each tunnel restart generates a new random `.lhr.life` subdomain, requiring redirect URI updates in TikTok portal.

## 2026-06-18: Note9 (SM-X210) como host 24/7 con ngrok + tmux
- Context: localhost.run cambia URL cada reinicio; inestable para revisión de TikTok que requiere URL fija. PC no está siempre encendido.
- Decision: Migrar Flask + ngrok al Note9 (arm64) que está encendido 24/7. ngrok con authtoken da URL persistente (`gravy-diaper-refrain.ngrok-free.dev`). tmux en Termux mantiene procesos vivos entre sesiones SSH.
- Consequence: URL fija para Redirect URI. PC ya no necesita procesos en segundo plano. Note9 se auto-arranca con Termux:Boot.

## 2026-05-26: Dynamic redirect URI from request headers
- Context: Tunnel URL changes every restart; hardcoding `REDIRECT_URI` in config.py required manual updates.
- Decision: Use `ProxyFix` middleware and resolve `redirect_uri` dynamically from `X-Forwarded-Proto` and `X-Forwarded-Host` headers at request time.
- Consequence: App works with any tunnel URL without config changes. Portal Redirect URI still needs manual sync.

## 2026-05-26: Flask debug=False, use_reloader=False
- Context: The reloader was creating duplicate processes that crashed the tunnel.
- Decision: Explicitly disable debug mode and reloader in production.
- Consequence: No hot-reload during development, but stable tunnel connections.

## 2026-05-26: Website on GitHub Pages, app behind tunnel
- Context: TikTok requires a public website with legal pages and login entry point.
- Decision: Host static site (index, privacy, terms, data-deletion) on GitHub Pages at `zerausn.github.io/agentes/`. Flask app runs behind SSH tunnel with dynamic URL.
- Consequence: Two separate domains — website is static on GitHub, app is on tunnel. Reviewers need to follow the login link to the tunnel.

## 2026-05-26: terms.html converted to directory for TikTok URL prefix verification
- Context: TikTok verification requires a file at `https://zerausn.github.io/agentes/terms.html/tiktok...txt`.
- Decision: Convert `terms.html` from a file to a directory (`terms.html/index.html`) with the verification file inside.
- Consequence: Terms URL is `https://zerausn.github.io/agentes/terms.html/` (with trailing slash).

## 2026-05-26: App icon on all website pages
- Context: TikTok review requires the app icon visible on browser tab (favicon) and header of all pages (Privacy, Terms, Data Deletion).
- Decision: Add `<link rel="icon">`, `<link rel="apple-touch-icon">`, and `<header class="app-header">` with app icon image to every HTML page.
- Consequence: All legal pages display the Uploaderbot brand consistently.

## 2026-05-26: Config.py refactored with PUBLIC_BASE_URL and env vars
- Context: Config had hardcoded values, making it inflexible for different tunnel URLs.
- Decision: Extract `PUBLIC_BASE_URL`, `REDIRECT_URI`, `PORT`, `DEBUG`, `SECRET_KEY` into environment variables with sensible defaults. Use a helper `_env_list()` for scopes.
- Consequence: Deployment config is now environment-driven; code works across environments without edits.
