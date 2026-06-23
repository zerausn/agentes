# TikTok Uploader - Architecture

## Overview
Flask web app that authenticates with TikTok OAuth and publishes videos via TikTok Content Posting API.

## Components

### Flask App (`app.py`)
- Routes: `/`, `/login`, `/login/basic`, `/callback`, `/upload`, `/api/init-upload`, `/api/upload-file`, `/api/publish`, `/logout`
- Dynamic redirect URI resolution via `X-Forwarded-*` headers (ProxyFix middleware)
- OAuth state stored in Flask session
- Access tokens kept in-memory (`TOKENS` dict), never persisted

### Configuration (`config.py`)
- Credentials from env vars with hardcoded fallbacks
- `PUBLIC_BASE_URL` controls the public-facing URL
- `REDIRECT_URI` derived from `PUBLIC_BASE_URL`
- Scopes: `user.info.basic`, `video.upload`, `video.publish`

### Templates
- `index.html` — login page with user profile display
- `upload.html` — drag-and-drop video upload + publish UI
- `callback_bridge.html` — JS redirect bridge for Cloudflare compatibility

### Tunnel
- localhost.run (SSH reverse tunnel) exposes `localhost:8080` to the internet
- Each restart generates a new random `.lhr.life` subdomain
- trapdoor.sh was used previously but abandoned due to persistent 429/502 errors

## TikTok API Flow
1. User visits `/login` → redirected to `https://www.tiktok.com/v2/auth/authorize/` with OAuth params
2. User authorizes → TikTok redirects to `/callback?code=...`
3. Server exchanges `code` for `access_token` via POST to `/v2/oauth/token/`
4. User sees upload page → selects video → `/api/init-upload` gets upload URL
5. Client PUTs video to upload URL → `/api/publish` triggers publication

## Data Flow
- **Authentication**: OAuth 2.0 Authorization Code flow
- **Video Upload**: Direct HTTP PUT to TikTok CDN (chunked upload not implemented — single chunk)
- **Publication**: POST to `/v2/post/publish/video/publish/` with `publish_id`
- **No persistent storage**: Tokens in memory only, no database

## Security
- CSRF protection via `state` param in OAuth
- Session-based auth for web UI
- `ProxyFix` middleware for correct scheme/host behind reverse proxy
- Debug mode disabled in production
