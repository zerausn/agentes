# AI & Developer Technical Reference (v2.1)

> **Purpose**: This repository automates bulk YouTube uploads for theatrical registries with a focus on resumable reliability and quota management.

## 🤖 AI Interaction Protocol
Any AI agent resuming this task MUST follow these rules:
1. **Config First**: Read `config.json` (local only) or `config.example.json` to verify `publish_hour` and exclusion patterns.
2. **Scanner Validation**: Run `video_scanner.py` periodically to sync the `scanned_videos.json` database.
3. **Resumable Uploads**: The `uploader.py` uses a chunked approach (10MB per chunk). If a network interruption occurs, the script will retry 5 times with exponential backoff.
4. **Metadata Rules**: Titles MUST follow the format `Project Name | [DATE] | ([FILENAME])`. Use `Path(video['filename']).stem` for the inner hash.

## 🛠️ Architecture Details
- **Quota Guard**: GCP Quotas are tracked in `quota_status.json`. The script automatically rotates through `client_secret_X.json` files in `credentials/` when a `403 QuotaExceeded` error is caught.
- **Audience Safety**: All uploads are hardcoded to `selfDeclaredMadeForKids: False` and `hasAlteredContentDisclosure: False` inside the insertion snippet for compliance.
- **Daily Scheduling**: The `get_next_publish_date` function calculates the slot based on the last scheduled video in the JSON database, maintaining exactly 24h separation.

## 👨‍💻 Developer Guide
- **Auth**: On first run with a new credential, a browser window (Edge preferred) will open for OAuth consent.
- **Logging**: Detailed logs are stored in `uploader.log`. Note: This file may contain private local paths and is gitignored.
- **Deployment**: Mark finished videos as `uploaded: true` in the DB. The script moves them to `videos subidos exitosamente`.

---
*Created and maintained by Antigravity AI Agent.*
