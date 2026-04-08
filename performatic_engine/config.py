"""
config.py - Configuración central del pipeline
===============================================
EDITA ESTE ARCHIVO con tus rutas y credenciales reales.
NUNCA commitees este archivo con secrets al repositorio.
Usa variables de entorno o Google Secret Manager para producción.
"""

import os
from dataclasses import dataclass, field
from pathlib import Path


# ---------------------------------------------------------------------------
# PROYECTOS DE GOOGLE CLOUD (uno por cada ~6 videos/día)
# Agrega aquí los client_secret JSON de cada proyecto.
# Puedes tener 10 proyectos = ~60 videos diarios vía API.
# ---------------------------------------------------------------------------
GOOGLE_PROJECTS = [
    {
        "project_id": "performatic-yt-01",
        "client_secret_file": "credentials/project_01_secret.json",
        "token_file": "credentials/project_01_token.json",
        "daily_quota_units": 10000,  # unidades totales por día
        "cost_per_upload": 1600,     # unidades que cuesta 1 video
    },
    {
        "project_id": "performatic-yt-02",
        "client_secret_file": "credentials/project_02_secret.json",
        "token_file": "credentials/project_02_token.json",
        "daily_quota_units": 10000,
        "cost_per_upload": 1600,
    },
    # --- Agrega hasta 10 proyectos ---
    # {
    #     "project_id": "performatic-yt-03",
    #     "client_secret_file": "credentials/project_03_secret.json",
    #     "token_file": "credentials/project_03_token.json",
    #     "daily_quota_units": 10000,
    #     "cost_per_upload": 1600,
    # },
]


@dataclass
class PipelineConfig:
    # --- Rutas ---
    output_dir: Path = Path("output")
    clips_dir: Path = Path("output/clips")
    normalized_dir: Path = Path("output/normalized")
    srt_dir: Path = Path("output/srt")
    metadata_dir: Path = Path("output/metadata")

    # --- Normalización ---
    target_fps: int = 30
    target_resolution: str = "1920:1080"  # se respeta solo si es mayor

    # --- Segmentación ---
    # "pyscenedetect" = rápido, "transnetv2" = preciso
    segmenter_backend: str = "pyscenedetect"
    scene_threshold: float = 27.0       # para pyscenedetect (HSV)
    min_scene_duration_s: float = 3.0   # ignora cortes < 3 segundos

    # --- Clips ---
    # Duraciones objetivo para los distintos formatos
    short_clip_min_s: float = 30.0
    short_clip_max_s: float = 90.0
    medium_clip_min_s: float = 300.0    # 5 min
    medium_clip_max_s: float = 600.0    # 10 min
    clips_per_video: int = 5            # máximo de clips a extraer por video

    # --- Transcripción (Whisper) ---
    whisper_model: str = "large-v3"     # base / small / medium / large-v3
    whisper_language: str = "es"
    whisper_device: str = "cuda"        # "cuda" o "cpu"
    # Activar whisper-timestamped para marcas de tiempo por palabra
    use_word_timestamps: bool = True

    # --- NLP / análisis de hooks ---
    spacy_model: str = "es_core_news_lg"
    # Palabras clave de alto impacto para detección de hooks
    hook_keywords: list = field(default_factory=lambda: [
        "secreto", "nunca", "jamás", "revelación", "por qué", "cómo",
        "error", "trampa", "descubrí", "nadie te dice", "la verdad",
        "cambió", "transformó", "increíble", "brutal", "histórico",
        "performático", "teatral", "real", "fake", "cuerpo", "poder",
    ])
    # Puntaje mínimo de "burstiness" para considerar un segmento como hook
    hook_burstiness_threshold: float = 0.65

    # --- Reencuadre 9:16 (YOLOv8) ---
    yolo_model: str = "yolov8n.pt"      # nano=rápido, yolov8x=preciso
    output_width: int = 1080
    output_height: int = 1920
    # Suavizado de seguimiento (0=sin suavizado, 1=completamente fijo)
    tracking_smoothing: float = 0.85
    # Regla de composición: "center", "golden_ratio", "thirds"
    composition_rule: str = "golden_ratio"

    # --- SMO / metadatos ---
    # Backend LLM para generar títulos, descripciones, tags
    # "anthropic" usa la API de Claude, "local" usa ollama/llama
    smo_backend: str = "anthropic"
    anthropic_model: str = "claude-sonnet-4-20250514"
    smo_language: str = "es"
    # Etiquetas base siempre incluidas en todos los videos
    base_tags: list = field(default_factory=lambda: [
        "teatro colombiano", "artes escénicas", "performático",
        "escrituras performáticas", "Cali Colombia", "performance",
        "dramaturgia", "arte contemporáneo",
    ])

    # --- Upload ---
    # Estrategia de rotación: "round_robin" o "quota_aware"
    # quota_aware revisa cuántas unidades quedan antes de asignar
    upload_rotation_strategy: str = "quota_aware"
    google_projects: list = field(default_factory=lambda: GOOGLE_PROJECTS)
    # Estado de cuota se persiste en este archivo para sobrevivir reinicios
    quota_state_file: Path = Path("credentials/quota_state.json")
    # Privacidad por defecto al subir
    default_privacy: str = "private"    # "private" / "unlisted" / "public"
    # Categoría YouTube: 27 = Educación, 24 = Entretenimiento
    default_category_id: str = "27"
    # Pausa entre uploads para evitar rate limiting
    upload_delay_s: float = 5.0

    # --- Formatos de salida adicionales ---
    generate_srt: bool = True
    generate_thumbnail: bool = False    # requiere Pillow + modelo adicional
    generate_chapters: bool = True      # capítulos en la descripción

    def __post_init__(self):
        for d in [self.output_dir, self.clips_dir, self.normalized_dir,
                  self.srt_dir, self.metadata_dir]:
            d.mkdir(parents=True, exist_ok=True)
        Path("credentials").mkdir(exist_ok=True)
