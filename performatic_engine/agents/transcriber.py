"""
agents/transcriber.py
=====================
Agente 3: Transcripción + Análisis Dramatúrgico de Hooks
- Whisper large-v3 para transcripción con marcas de tiempo por palabra
- spaCy es_core_news_lg para análisis NLP en español
- Detección de "burstiness" y vacíos de curiosidad
- Lógica de "Promesa, Prueba, Camino" para selección de clips
"""

import logging
import json
import math
from pathlib import Path

log = logging.getLogger(__name__)

# Prompt maestro de dirección dramatúrgica para el agente LLM
DRAMATURG_PROMPT = """Actúa como un Dramaturgo Digital e Ingeniero de Atención con doctorado
en Artes Escénicas y Sociología. Analiza la siguiente transcripción de un video pilar.

Identifica los {n_clips} segmentos más potentes de entre {min_s} y {max_s} segundos
que funcionen como 'escenas de iniciación'. Cada segmento debe contener:
1. Un vacío de curiosidad inicial (hook en los primeros 3 segundos)
2. Una progresión de 'Stance': de autor a director
3. Un pico emocional detectado por intensidad del lenguaje
4. Aplicar la teoría del 2+2: no revelar la conclusión prematuramente

Usa el modelo de "Promesa, Prueba, Camino" para validar cada selección.

Para cada clip retorna JSON con este formato exacto:
{{
  "clips": [
    {{
      "start_s": float,
      "end_s": float,
      "hook_text": "frase del gancho inicial",
      "burstiness_score": float entre 0 y 1,
      "reframe_suggestion": "cerrado|medio|panorámico",
      "emotional_peak_s": float,
      "promise": "qué promete el clip",
      "curiosity_gap": "qué deja sin resolver"
    }}
  ]
}}

TRANSCRIPCIÓN:
{transcript}
"""


class TranscriberAgent:
    def __init__(self, cfg):
        self.cfg = cfg
        self._whisper_model = None
        self._nlp = None

    @property
    def whisper(self):
        if self._whisper_model is None:
            log.info(f"  Cargando Whisper {self.cfg.whisper_model}...")
            if self.cfg.use_word_timestamps:
                import whisper_timestamped as whisper
                self._whisper_model = whisper.load_model(
                    self.cfg.whisper_model,
                    device=self.cfg.whisper_device,
                )
            else:
                import whisper
                self._whisper_model = whisper.load_model(
                    self.cfg.whisper_model,
                    device=self.cfg.whisper_device,
                )
        return self._whisper_model

    @property
    def nlp(self):
        if self._nlp is None:
            import spacy
            log.info(f"  Cargando spaCy {self.cfg.spacy_model}...")
            self._nlp = spacy.load(self.cfg.spacy_model)
        return self._nlp

    def run(self, video_path: Path, scenes: list[dict]) -> dict:
        # Transcripción completa con marcas de tiempo
        log.info("  Transcribiendo audio...")
        transcript_data = self._transcribe(video_path)

        # Serializar para caché
        cache_path = self.cfg.output_dir / f"{video_path.stem}_transcript.json"
        cache_path.write_text(json.dumps(transcript_data, ensure_ascii=False, indent=2))

        # Análisis de hooks usando spaCy + heurísticas
        log.info("  Analizando hooks y burstiness...")
        hooks = self._detect_hooks(transcript_data, scenes)

        # Refinar con LLM si está disponible
        if self.cfg.smo_backend == "anthropic":
            hooks = self._refine_with_llm(transcript_data["full_text"], hooks)

        # Generar SRT
        if self.cfg.generate_srt:
            srt_path = self.cfg.srt_dir / f"{video_path.stem}.srt"
            self._export_srt(transcript_data, srt_path)
            log.info(f"  SRT exportado: {srt_path}")

        return {
            "full_text": transcript_data["full_text"],
            "words": transcript_data.get("words", []),
            "segments": transcript_data.get("segments", []),
            "hooks": hooks,
            "cache_path": str(cache_path),
        }

    def _transcribe(self, video_path: Path) -> dict:
        """Extrae audio y transcribe con Whisper."""
        import subprocess
        import tempfile
        import os

        # Extraer audio temporalmente
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
            tmp_audio = tmp.name

        subprocess.run([
            "ffmpeg", "-y", "-i", str(video_path),
            "-ar", "16000", "-ac", "1", "-c:a", "pcm_s16le",
            tmp_audio,
        ], check=True, capture_output=True)

        try:
            if self.cfg.use_word_timestamps:
                import whisper_timestamped as whisper
                result = whisper.transcribe(
                    self.whisper, tmp_audio,
                    language=self.cfg.whisper_language,
                    detect_disfluencies=True,
                )
            else:
                result = self.whisper.transcribe(
                    tmp_audio,
                    language=self.cfg.whisper_language,
                    word_timestamps=True,
                )
        finally:
            os.unlink(tmp_audio)

        # Normalizar estructura
        words = []
        for seg in result.get("segments", []):
            for w in seg.get("words", []):
                words.append({
                    "word": w.get("text", "").strip(),
                    "start": w.get("start", 0),
                    "end": w.get("end", 0),
                    "confidence": w.get("confidence", 1.0),
                })

        return {
            "full_text": result.get("text", ""),
            "segments": result.get("segments", []),
            "words": words,
            "language": result.get("language", "es"),
        }

    def _detect_hooks(self, transcript_data: dict, scenes: list[dict]) -> list[dict]:
        """
        Análisis heurístico de hooks usando spaCy y palabras clave.
        Calcula un score de burstiness por escena.
        """
        full_text = transcript_data["full_text"]
        words = transcript_data.get("words", [])
        hooks = []

        for scene in scenes:
            # Palabras en este rango temporal
            scene_words = [
                w for w in words
                if scene["start_s"] <= w["start"] <= scene["end_s"]
            ]
            scene_text = " ".join(w["word"] for w in scene_words)
            if not scene_text.strip():
                continue

            # Análisis NLP
            doc = self.nlp(scene_text[:5000])  # límite spaCy

            # Calcular burstiness: densidad de keywords + entidades + verbos fuertes
            keyword_hits = sum(
                1 for kw in self.cfg.hook_keywords
                if kw.lower() in scene_text.lower()
            )
            entity_count = len(doc.ents)
            verb_count = sum(1 for t in doc if t.pos_ == "VERB")
            word_count = max(len(scene_words), 1)

            burstiness = min(1.0, (
                (keyword_hits * 0.4) +
                (entity_count / word_count * 0.3) +
                (verb_count / word_count * 0.3)
            ))

            if burstiness >= self.cfg.hook_burstiness_threshold:
                # Encontrar la frase de gancho (primeras 2 oraciones)
                sentences = list(doc.sents)
                hook_text = str(sentences[0]) if sentences else scene_text[:80]

                # Pico emocional: momento con mayor densidad de keywords
                emotional_peak_s = self._find_emotional_peak(
                    scene_words, scene["start_s"]
                )

                hooks.append({
                    "start_s": scene["start_s"],
                    "end_s": scene["end_s"],
                    "duration_s": scene["duration_s"],
                    "hook_text": hook_text.strip(),
                    "burstiness_score": round(burstiness, 3),
                    "scene_text": scene_text,
                    "reframe_suggestion": "cerrado",  # default, LLM lo refina
                    "emotional_peak_s": emotional_peak_s,
                    "promise": "",
                    "curiosity_gap": "",
                })

        # Ordenar por burstiness, tomar los mejores N
        hooks.sort(key=lambda h: h["burstiness_score"], reverse=True)
        return hooks[:self.cfg.clips_per_video]

    def _find_emotional_peak(self, words: list, start_s: float) -> float:
        """Encuentra el segundo con mayor densidad de palabras clave."""
        if not words:
            return start_s
        keyword_set = set(kw.lower() for kw in self.cfg.hook_keywords)
        best_time = start_s
        best_count = 0
        window = 5.0  # ventana de 5 segundos
        times = [w["start"] for w in words]
        for t in times:
            count = sum(
                1 for w in words
                if t <= w["start"] <= t + window
                and any(kw in w["word"].lower() for kw in keyword_set)
            )
            if count > best_count:
                best_count = count
                best_time = t
        return round(best_time, 2)

    def _refine_with_llm(self, full_text: str, hooks: list[dict]) -> list[dict]:
        """
        Envía la transcripción al LLM para análisis dramatúrgico profundo.
        Enriquece los hooks con promise, curiosity_gap, y reframe_suggestion.
        """
        try:
            import anthropic
            client = anthropic.Anthropic()

            prompt = DRAMATURG_PROMPT.format(
                n_clips=self.cfg.clips_per_video,
                min_s=int(self.cfg.short_clip_min_s),
                max_s=int(self.cfg.short_clip_max_s),
                transcript=full_text[:8000],  # límite de contexto práctico
            )

            response = client.messages.create(
                model=self.cfg.anthropic_model,
                max_tokens=2000,
                messages=[{"role": "user", "content": prompt}],
            )

            raw = response.content[0].text
            # Extraer JSON de la respuesta
            import re
            json_match = re.search(r'\{.*\}', raw, re.DOTALL)
            if json_match:
                llm_data = json.loads(json_match.group())
                llm_clips = llm_data.get("clips", [])

                # Fusionar datos LLM con hooks detectados localmente
                for i, hook in enumerate(hooks):
                    if i < len(llm_clips):
                        llm_clip = llm_clips[i]
                        hook["reframe_suggestion"] = llm_clip.get(
                            "reframe_suggestion", hook.get("reframe_suggestion", "cerrado")
                        )
                        hook["promise"] = llm_clip.get("promise", "")
                        hook["curiosity_gap"] = llm_clip.get("curiosity_gap", "")
                        hook["burstiness_score"] = max(
                            hook["burstiness_score"],
                            float(llm_clip.get("burstiness_score", 0)),
                        )

        except Exception as e:
            log.warning(f"  LLM refinement falló: {e}. Usando análisis local.")

        return hooks

    def _export_srt(self, transcript_data: dict, srt_path: Path):
        """Exporta subtítulos SRT de alta fidelidad (generados localmente con Whisper)."""
        segments = transcript_data.get("segments", [])
        lines = []
        for i, seg in enumerate(segments, 1):
            start = self._seconds_to_srt_time(seg["start"])
            end = self._seconds_to_srt_time(seg["end"])
            text = seg.get("text", "").strip()
            lines.append(f"{i}\n{start} --> {end}\n{text}\n")
        srt_path.write_text("\n".join(lines), encoding="utf-8")

    @staticmethod
    def _seconds_to_srt_time(s: float) -> str:
        h = int(s // 3600)
        m = int((s % 3600) // 60)
        sec = int(s % 60)
        ms = int((s - int(s)) * 1000)
        return f"{h:02d}:{m:02d}:{sec:02d},{ms:03d}"
