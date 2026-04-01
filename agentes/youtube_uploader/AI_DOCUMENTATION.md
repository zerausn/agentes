# AI Architecture & Context Documentation
> **Target Audience:** Future AI Agents (Gemini, Claude, GPT-4) reading this repository to resume operations for the user `zerausn`.

## System Overview
This repository contains a YouTube Bulk-Uploader with automated staggered scheduling, built to circumvent the severe constraints of the YouTube Data API v3 (10,000 quota units / 6 videos per day per GCP Project).

- **Objective**: The user (`zerausn`) wants to upload ~18 heavy videos daily (`.mp4`, `.mkv`) for their theater/performance arts channel (`escriturasperformaticascali@gmail.com`).
- **Core Strategy**: 
  1. The user manually creates 1 to 3+ Google Cloud Projects and downloads their OAuth 2.0 Client ID JSONs.
  2. The script locally scans the user's hard drive for videos > 100MB and tracks state via `scanned_videos.json`.
  3. `uploader.py` auths the first GCP Project. It uploads 6 videos using `MediaFileUpload(resumable=True)` to prevent timeouts on massive files.
  4. Once it hits `quotaExceeded` or `rateLimitExceeded` (HTTP 403), the python script intercepts the error, catches the specific quota JSON response, and cleanly gracefully rotates to the next `client_secret_{next}.json` key in the pool to continue uploading the remaining batch without human intervention.
  5. The videos are uploaded as `private` and scheduled to go public at **17:45 UTC-5 (Colombia Time)** incrementally (+1 day for every video uploaded) using the `publishAt` property. 
  6. Upon completion, the local file is moved into a `./videos subidos exitosamente` nested directory to clear the workspace.

## AI Execution Instructions
If the user asks you to "run the uploader", "check the queue", or "continue where we left off", follow this workflow:

1. **Verify VENV**: Always ensure Python is running inside the `C:\Users\ZN\Documents\Antigravity\venv` environment, as that is where `google-api-python-client` and `google-auth-oauthlib` are globally installed for all Antigravity agents.
2. **Scan**: Run `python video_scanner.py` to index the user's drives. It will append securely to `scanned_videos.json`.
3. **Upload**: Run `python uploader.py`. **WARNING:** If it's the first time running a new `client_secret_X.json`, the flow requires the user to click through a browser window to approve the OAuth scope. *Instruct the user to expect a local browser popup.*
4. **Git Operations**: **NEVER commit `credentials/` or `*.json`**. The `.gitignore` is heavily fortified to reject them, but do not override it. Leaking the user's Client ID will result in API quota theft or bans.

## Environment Variables
- Ensure `USERPROFILE` path is mapped correctly when looking for Video Roots if scanning fails. 
- Python version target is >= `3.11`.
