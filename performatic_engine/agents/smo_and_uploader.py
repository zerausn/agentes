"""
agents/smo_generator.py
=======================
Agente 5: Generación de metadatos SMO (Social Media Optimization)
- Títulos con Video SEO: keyword frontal, emoción, número
- Descripción estructurada: hook + capítulos + CTA
- Tags optimizados para YouTube + AEO (Answer Engine Optimization)
- Generado por Claude Sonnet para máxima calidad en español
"""

import json
import logging
import re
from pathlib import Path

log = logging.getLogger(__name__)

SMO_PROMPT = """Eres un experto en Video SEO y Social Media Optimization (SMO) para YouTube
en español latinoamericano. Trabajas para el canal "Performatic Writings" de artes escénicas
y dramaturgia de Cali, Colombia.

Genera metadatos optimizados para este clip de video.
Contexto del clip:
- Hook principal: {hook_text}
- Promesa del clip: {promise}
- Vacío de curiosidad: {curiosity_gap}
- Duración: {duration_s:.0f} segundos
- Tags base del canal: {base_tags}

Genera en JSON exacto (sin markdown, sin explicaciones):
{{
  "title": "Título de máximo 70 chars, keyword al inicio, genera curiosidad, incluye número o poder emocional",
  "description": "Descripción de 3 párrafos:\\n1. Hook (2 oraciones que amplían el título)\\n2. Contenido del clip (qué aprende el espectador)\\n3. CTA: suscribirse + link a canal\\n\\nCapítulos si aplica:\\n0:00 Intro\\n...",
  "tags": ["tag1", "tag2", ...lista de 15 tags SEO relevantes...],
  "hashtags": ["#hashtag1", "#hashtag2", "#hashtag3"],
  "thumbnail_text": "Texto de 3-5 palabras para el thumbnail (impacto visual)",
  "category": "artes escénicas|dramaturgia|performance|teatro"
}}"""


class SMOGeneratorAgent:
    def __init__(self, cfg):
        self.cfg = cfg

    def run(self, clips: list[dict], transcript_data: dict | None) -> list[dict]:
        enriched = []
        for i, clip in enumerate(clips):
            log.info(f"  Generando SMO para clip {i+1}/{len(clips)}...")
            metadata = self._generate_metadata(clip)
            clip["metadata"] = metadata

            # Guardar metadata en disco
            meta_path = (
                self.cfg.metadata_dir
                / f"{Path(clip['path']).stem}_metadata.json"
            )
            meta_path.write_text(
                json.dumps(metadata, ensure_ascii=False, indent=2)
            )
            clip["metadata_path"] = str(meta_path)
            enriched.append(clip)
        return enriched

    def _generate_metadata(self, clip: dict) -> dict:
        if self.cfg.smo_backend == "anthropic":
            return self._generate_with_claude(clip)
        return self._generate_fallback(clip)

    def _generate_with_claude(self, clip: dict) -> dict:
        try:
            import anthropic
            client = anthropic.Anthropic()

            prompt = SMO_PROMPT.format(
                hook_text=clip.get("hook_text", "")[:200],
                promise=clip.get("promise", "")[:200],
                curiosity_gap=clip.get("curiosity_gap", "")[:200],
                duration_s=clip.get("end_s", 0) - clip.get("start_s", 0),
                base_tags=", ".join(self.cfg.base_tags),
            )

            response = client.messages.create(
                model=self.cfg.anthropic_model,
                max_tokens=1000,
                messages=[{"role": "user", "content": prompt}],
            )

            raw = response.content[0].text
            json_match = re.search(r'\{.*\}', raw, re.DOTALL)
            if json_match:
                data = json.loads(json_match.group())
                # Asegurar que los tags base siempre están incluidos
                all_tags = list(set(
                    self.cfg.base_tags + data.get("tags", [])
                ))[:50]  # YouTube permite máx 500 chars en tags
                data["tags"] = all_tags
                return data

        except Exception as e:
            log.warning(f"  Claude SMO falló: {e}")

        return self._generate_fallback(clip)

    def _generate_fallback(self, clip: dict) -> dict:
        """Fallback determinístico si el LLM no está disponible."""
        hook = clip.get("hook_text", "Clip de artes escénicas")[:60]
        return {
            "title": f"{hook} | Performatic Writings",
            "description": (
                f"{hook}\n\n"
                "Canal de escrituras performáticas, dramaturgia y artes escénicas "
                "desde Cali, Colombia.\n\n"
                "🔔 Suscríbete: https://youtube.com/@performaticwritings"
            ),
            "tags": self.cfg.base_tags + ["clipping", "shorts", "dramaturgia digital"],
            "hashtags": ["#teatro", "#performance", "#Colombia"],
            "thumbnail_text": hook[:30],
            "category": "artes escénicas",
        }


# =============================================================================

"""
agents/uploader.py
==================
Agente 6: Upload con rotación de cuota entre proyectos Google Cloud
- Estrategia quota_aware: calcula unidades restantes antes de asignar
- Persiste estado de cuota en JSON para sobrevivir reinicios
- OAuth 2.0 flow con refresh automático de tokens
- Soporte para título, descripción, tags, categoría, privacidad
- SRT upload como subtítulos
"""

import json
import logging
import time
from datetime import date
from pathlib import Path

log = logging.getLogger(__name__)


class QuotaManager:
    """Gestiona el estado de cuota de cada proyecto Google Cloud."""

    def __init__(self, projects: list[dict], state_file: Path):
        self.projects = projects
        self.state_file = state_file
        self.state = self._load_state()

    def _load_state(self) -> dict:
        today = str(date.today())
        if self.state_file.exists():
            data = json.loads(self.state_file.read_text())
            # Resetear si es un día nuevo
            if data.get("date") != today:
                return self._fresh_state(today)
            return data
        return self._fresh_state(today)

    def _fresh_state(self, today: str) -> dict:
        return {
            "date": today,
            "projects": {
                p["project_id"]: {
                    "units_used": 0,
                    "units_total": p["daily_quota_units"],
                    "uploads_today": 0,
                }
                for p in self.projects
            },
        }

    def _save(self):
        self.state_file.write_text(
            json.dumps(self.state, indent=2)
        )

    def get_available_project(self, cost_units: int = 1600) -> dict | None:
        """Retorna el proyecto con más cuota disponible."""
        best = None
        best_remaining = 0

        for project in self.projects:
            pid = project["project_id"]
            proj_state = self.state["projects"].get(pid, {})
            used = proj_state.get("units_used", 0)
            total = proj_state.get("units_total", project["daily_quota_units"])
            remaining = total - used

            if remaining >= cost_units and remaining > best_remaining:
                best = project
                best_remaining = remaining

        return best

    def record_upload(self, project_id: str, cost_units: int = 1600):
        if project_id in self.state["projects"]:
            self.state["projects"][project_id]["units_used"] += cost_units
            self.state["projects"][project_id]["uploads_today"] += 1
            self._save()

    def summary(self) -> str:
        lines = [f"Cuota del día {self.state['date']}:"]
        for pid, s in self.state["projects"].items():
            remaining = s["units_total"] - s["units_used"]
            lines.append(
                f"  {pid}: {s['uploads_today']} videos, "
                f"{remaining}/{s['units_total']} unidades restantes"
            )
        return "\n".join(lines)


class UploaderAgent:
    def __init__(self, cfg):
        self.cfg = cfg
        self.quota = QuotaManager(
            cfg.google_projects,
            cfg.quota_state_file,
        )

    def run(self, clips: list[dict]) -> list[dict]:
        results = []
        log.info(self.quota.summary())

        for i, clip in enumerate(clips):
            project = self.quota.get_available_project()
            if not project:
                log.warning(
                    f"  Sin cuota disponible para clip {i+1}. "
                    "Agrega más proyectos o espera al día siguiente."
                )
                results.append({
                    "clip": clip["path"],
                    "status": "quota_exhausted",
                    "video_id": None,
                })
                continue

            log.info(
                f"  Subiendo clip {i+1}/{len(clips)} → {project['project_id']}"
            )
            result = self._upload_clip(clip, project)
            results.append(result)

            if result["status"] == "ok":
                self.quota.record_upload(project["project_id"])
                log.info(f"  ✓ Subido: https://youtu.be/{result['video_id']}")

                # Subir SRT si existe
                if clip.get("srt_path") and result.get("video_id"):
                    self._upload_srt(
                        result["video_id"],
                        clip["srt_path"],
                        project,
                    )

            time.sleep(self.cfg.upload_delay_s)

        log.info(self.quota.summary())
        return results

    def _get_youtube_client(self, project: dict):
        """Construye el cliente YouTube con OAuth 2.0 y refresh automático."""
        from google.oauth2.credentials import Credentials
        from google.auth.transport.requests import Request
        from google_auth_oauthlib.flow import InstalledAppFlow
        from googleapiclient.discovery import build

        SCOPES = ["https://www.googleapis.com/auth/youtube.upload",
                  "https://www.googleapis.com/auth/youtube.force-ssl"]

        token_file = Path(project["token_file"])
        secret_file = Path(project["client_secret_file"])
        creds = None

        if token_file.exists():
            creds = Credentials.from_authorized_user_file(str(token_file), SCOPES)

        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                if not secret_file.exists():
                    raise FileNotFoundError(
                        f"No se encontró: {secret_file}\n"
                        "Descarga el client_secret.json desde Google Cloud Console."
                    )
                flow = InstalledAppFlow.from_client_secrets_file(
                    str(secret_file), SCOPES
                )
                creds = flow.run_local_server(port=0)

            token_file.write_text(creds.to_json())

        return build("youtube", "v3", credentials=creds)

    def _upload_clip(self, clip: dict, project: dict) -> dict:
        """Sube el video a YouTube con metadatos SMO completos."""
        from googleapiclient.http import MediaFileUpload

        clip_path = Path(clip["path"])
        metadata = clip.get("metadata", {})

        try:
            youtube = self._get_youtube_client(project)

            body = {
                "snippet": {
                    "title": metadata.get("title", clip_path.stem)[:100],
                    "description": metadata.get("description", "")[:5000],
                    "tags": metadata.get("tags", self.cfg.base_tags)[:500],
                    "categoryId": self.cfg.default_category_id,
                    "defaultLanguage": "es",
                    "defaultAudioLanguage": "es",
                },
                "status": {
                    "privacyStatus": self.cfg.default_privacy,
                    "selfDeclaredMadeForKids": False,
                    "madeForKids": False,
                },
            }

            media = MediaFileUpload(
                str(clip_path),
                mimetype="video/mp4",
                resumable=True,
                chunksize=10 * 1024 * 1024,  # chunks de 10MB
            )

            request = youtube.videos().insert(
                part="snippet,status",
                body=body,
                media_body=media,
            )

            response = None
            while response is None:
                status, response = request.next_chunk()
                if status:
                    pct = int(status.progress() * 100)
                    log.debug(f"    Upload: {pct}%")

            return {
                "clip": str(clip_path),
                "status": "ok",
                "video_id": response.get("id"),
                "project_id": project["project_id"],
                "title": body["snippet"]["title"],
            }

        except Exception as e:
            log.error(f"  Error subiendo {clip_path.name}: {e}")
            return {
                "clip": str(clip_path),
                "status": "error",
                "error": str(e),
                "video_id": None,
            }

    def _upload_srt(self, video_id: str, srt_path: str, project: dict):
        """Sube subtítulos SRT de alta fidelidad al video."""
        from googleapiclient.http import MediaFileUpload

        try:
            youtube = self._get_youtube_client(project)
            media = MediaFileUpload(srt_path, mimetype="application/x-subrip")
            youtube.captions().insert(
                part="snippet",
                body={
                    "snippet": {
                        "videoId": video_id,
                        "language": "es",
                        "name": "Español (auto-Whisper)",
                        "isDraft": False,
                    }
                },
                media_body=media,
            ).execute()
            log.info(f"  ✓ SRT subido para {video_id}")
        except Exception as e:
            log.warning(f"  SRT upload falló: {e}")
