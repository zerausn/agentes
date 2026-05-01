# Performatic Content Engine
## Motor de Contenido Automatizado — Canal: Performatic Writings

Pipeline completo: video pilar → clips 9:16 → metadatos SMO → upload YouTube

---

## Arquitectura de Agentes

```
video.mp4
   │
   ▼
[Agente 1: Normalizer]     ffmpeg/ffprobe → VFR→CFR
   │
   ▼
[Agente 2: Segmenter]      PySceneDetect / TransNetV2 → lista de escenas
   │
   ▼
[Agente 3: Transcriber]    Whisper large-v3 + spaCy → hooks con timestamps
   │                        + LLM dramatúrgico (Claude) → promise/curiosity_gap
   ▼
[Agente 4: Reframer]       YOLOv8 + OpenCV → clips 9:16 reencuadrados
   │
   ▼
[Agente 5: SMOGenerator]   Claude Sonnet → título SEO + descripción + tags
   │
   ▼
[Agente 6: Uploader]       YouTube Data API v3 + rotación de proyectos
                            (~6 videos/proyecto/día × N proyectos)
```

---

## Setup inicial (una sola vez)

### 1. Instalar dependencias

```bash
# En Parrot OS / Debian
pip install -r requirements.txt --break-system-packages

# Modelo spaCy en español
python -m spacy download es_core_news_lg

# Modelo YOLOv8 (se descarga automáticamente al primer uso)
# Si quieres descargarlo manual:
# python -c "from ultralytics import YOLO; YOLO('yolov8n.pt')"
```

### 2. Crear credenciales de Google Cloud

Para cada proyecto (repite N veces para N × 6 videos/día):

```bash
# Crear proyecto
gcloud projects create performatic-yt-01 --name="Performatic YT 01"
gcloud config set project performatic-yt-01

# Habilitar YouTube Data API v3 (una vez por proyecto)
gcloud services enable youtube.googleapis.com

# Ir a Google Cloud Console → APIs & Services → Credentials
# → Create Credentials → OAuth 2.0 Client ID
# → Application type: Desktop app
# → Descargar JSON → guardar como credentials/project_01_secret.json
```

La primera vez que corras el pipeline, se abrirá un browser para autorizar
cada proyecto con tu cuenta escriturasperformaticascali@gmail.com.
El token se guarda en credentials/project_XX_token.json para usos futuros.

### 3. Configurar config.py

Edita `GOOGLE_PROJECTS` en `config.py` con las rutas de tus archivos secret.
Agrega hasta 10 proyectos para ~60 videos diarios.

### 4. Variable de entorno para Claude (SMO)

```bash
export ANTHROPIC_API_KEY="sk-ant-..."
```

---

## Uso

### Pipeline completo (recomendado)
```bash
python main.py --input /ruta/a/video.mp4 --mode full
```

### Solo generar clips (sin subir)
```bash
python main.py --input /ruta/a/video.mp4 --mode clips_only
```

### Solo subir clips ya procesados
```bash
python main.py --mode upload_only --clips_dir ./output/clips
```

---

## Estructura de salida

```
output/
├── normalized/          # video fuente normalizado a CFR
├── clips/               # clips 9:16 finales
│   ├── video_clip01.mp4
│   ├── video_clip02.mp4
│   └── ...
├── srt/                 # subtítulos de alta fidelidad (Whisper)
├── metadata/            # JSON con título, descripción, tags por clip
└── video_transcript.json
credentials/
├── project_01_secret.json   # NO commitear al repo
├── project_01_token.json    # NO commitear al repo
└── quota_state.json         # estado de cuota del día
pipeline.log
```

---

## Cuota YouTube Data API v3

| Acción | Costo (unidades) |
|--------|-----------------|
| Subir video | 1,600 |
| Subir subtítulos | 400 |
| Leer estadísticas | 1 |
| **Cuota diaria por proyecto** | **10,000** |
| **Videos/día por proyecto** | **~6** |

Con 10 proyectos: ~60 videos/día.

---

## Notas para Codex / Antigravity

- El punto de entrada es `main.py`
- Cada agente es independiente y testeable: `from agents.transcriber import TranscriberAgent`
- La config se centraliza en `config.py` — modificar ahí primero
- El uploader rota proyectos automáticamente según cuota disponible
- Los tokens OAuth se refrescan automáticamente sin intervención manual
- El estado de cuota persiste en `credentials/quota_state.json`
- En modo `upload_only`, los clips se leen de `--clips_dir` (útil para re-intentos)
