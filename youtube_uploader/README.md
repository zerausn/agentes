# YouTube Uploader — Performatic Writings

Sistema automatizado de subida de videos artísticos a YouTube.

## Inicio Rápido

```powershell
# 1. (Primera vez) Copiar y configurar:
Copy-Item config.example.json config.json
# Editar config.json con tus datos

# 2. Escanear videos:
python video_scanner.py

# 3. Sincronizar con canal (evita duplicados):
python check_channel_videos.py

# 4. Limpiar lista:
python clean_json.py

# 5. ¡Subir!
python uploader.py
```

## 🛑 Para detener la subida en cualquier momento:

```powershell
New-Item STOP -ItemType File
```
Para reanudar: `Remove-Item STOP`

## Documentación completa
Ver [AI.md](AI.md) y la carpeta [docs](docs).

## Privacidad
Los archivos `config.json`, `credentials/` y `*.log` están excluidos de Git.
