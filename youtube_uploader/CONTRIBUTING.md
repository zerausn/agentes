# Contributing to Agentes YouTube Uploader

## How to add new features
1. **Metadata Overrides**: If you need per-video description overrides, create a `.txt` file with the same name as the video in the same folder.
2. **Scanner Filters**: Add new exclusion patterns to the `scanner` object in `config.json`.
3. **New Credentials**: Add more `client_secret_N.json` files to the `credentials/` folder to increase the daily upload capacity.

## Safety First
- **DO NOT** commit `config.json` or `credentials/`.
- Ensure `scanned_videos.json` is updated before committing if you have performed a full disk scan.
