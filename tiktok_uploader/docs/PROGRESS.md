# TikTok Uploader — Progress

## Goal
Publicar videos en TikTok via Content Posting API y configurar cuenta creador con monetización, incluyendo registro y aprobación de la app Uploaderbot en TikTok Developers.

## Status: APP REVIEW REJECTED (attempt #2)

### What's Working
- Flask app with OAuth login (user.info.basic, video.upload, video.publish scopes)
- Video upload via Content Posting API (single chunk, FILE_UPLOAD)
- Video publication with configurable privacy level (SELF_ONLY enforced in sandbox)
- Dynamic redirect URI resolution from request headers
- localhost.run tunnel exposing the app on a public URL
- GitHub Pages website at `https://zerausn.github.io/agentes/` with:
  - App icon in header + favicon on all pages
  - Login button linking to the tunnel
  - Privacy Policy, Terms of Service, Data Deletion pages
  - TikTok URL prefix verification (meta tag + file)

### Review Issues (2026-06-18)
1. **Login entry point missing**: Button links to `uploaderbot.trapdoor.sh` which is down (429/502). Reviewer cannot test login flow.
2. **App icon**: Reviewer claims icon not visible on Privacy Policy / Terms pages (may have checked old version before latest gh-pages update).
3. **Insufficient Review Description**: Need detailed explanation of scopes and data usage.

#### Infrastructure Changes
- Note9 (SM-X210) configured as 24/7 host for TikTok stack
- ngrok installed on Note9 with authtoken, URL: `https://gravy-diaper-refrain.ngrok-free.dev`
- tmux sessions set up on Note9 for Flask + ngrok persistence
- Termux:Boot script created (`~/.termux/boot/start_tiktok.sh`) for auto-start on reboot
- Shortcut created (`Iniciar_TikTok.sh`) for manual restart
- PC processes (localhost.run tunnel, local Flask) killed — now using Note9 exclusively for 24/7 operation

## Previously Resolved
- App icon + favicon + header icon added to all website pages
- Website URL verification with TikTok (meta tag + TXT file + redirect URL)
- Products added to portal: Login Kit, Content Posting API, Share Kit
- PR #3 merged to main (add-tiktok-verify)
- Video demo recorded with SimpleScreenRecorder
- Flask `debug=False`, `use_reloader=False` to prevent crashes
- `config.py` refactored with env vars and `PUBLIC_BASE_URL`

## Next Steps
1. Update login button URL in website to current working tunnel
2. Push updated website to gh-pages
3. Write comprehensive review description
4. Resubmit app review in TikTok Developers Portal
5. Wait for approval, then configure monetization

## Blockers
- **Tunnel instability**: localhost.run URL changes every restart; trapdoor.sh unreliable
- **Redirect URI**: Must be updated manually in TikTok portal when tunnel changes
- **Sandbox limitation**: Content Posting API only allows `SELF_ONLY` privacy in sandbox mode
- **Parrot OS**: Chrome blocks TikTok JS; Firefox safe-mode needed for portal access
