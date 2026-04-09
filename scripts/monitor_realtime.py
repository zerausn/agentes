"""Monitor en tiempo real para Meta y YouTube.

Lee los logs locales existentes y presenta, por consola, el estado actual de
subida, el progreso actual, las subidas exitosas de hoy y el tiempo transcurrido
desde la ultima subida confirmada.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Iterable, Optional


LOG_LINE_RE = re.compile(
    r"^(?P<ts>\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2},\d{3}) - (?P<level>[A-Z]+) - (?P<msg>.*)$"
)

FB_CONFIRM_RE = re.compile(
    r"Facebook transfer confirmado hasta (?P<confirmed>\d+)/(?P<total>\d+) bytes para (?P<file>.+?) en (?P<seconds>[\d.]+)s \((?P<rate>[\d.]+) MB/s\)\."
)
FB_CHUNK_RE = re.compile(
    r"Facebook transfer chunk (?P<start>\d+)-(?P<end>\d+)/(?P<total>\d+) para (?P<file>.+)$"
)
FB_SUCCESS_RE = re.compile(
    r"Facebook confirmo (?:el video (?P<video_id>\d+) como programado para (?P<scheduled>.+?)|la programacion del video (?P<video_id_alt>\d+)|la publicacion del video (?P<video_id_pub>\d+))\."
)
FB_EXISTING_REMOTE_RE = re.compile(r"ya existia remoto con id (?P<video_id>\d+)")

IG_ACCEPT_RE = re.compile(r"Instagram acepto la publicacion\. Media ID: (?P<media_id>\d+)")
IG_START_RE = re.compile(r"Subiendo a Instagram \(ID: (?P<item>.+?)\)")
IG_USING_FILE_RE = re.compile(r"Usando archivo 1080p ya existente: (?P<item>.+)$")
IG_TRANSCODING_RE = re.compile(r"Transcodificando a 1080p: (?P<item>.+)$")
IG_TRANS_DONE_RE = re.compile(r"Transcodificación completada: (?P<item>.+)$")
IG_SKIP_RE = re.compile(
    r"Se omite instagram_feed para (?P<item>.+?) en jornada 1: (?P<reason>.+)$"
)

YT_START_RE = re.compile(r"^Iniciando subida: (?P<title>.+)$")
YT_PROGRESS_RE = re.compile(r"^Progreso: (?P<pct>\d+)%$")
YT_SUCCESS_RE = re.compile(r"^Subida completada\. Video ID: (?P<video_id>[\w-]+)$")
YT_PROGRAMMED_RE = re.compile(r"^Programado para: (?P<scheduled>.+)$")


def parse_log_timestamp(raw: str) -> datetime:
    return datetime.strptime(raw, "%Y-%m-%d %H:%M:%S,%f")


def format_duration(seconds: float) -> str:
    total = int(max(0, seconds))
    days, remainder = divmod(total, 86400)
    hours, remainder = divmod(remainder, 3600)
    minutes, secs = divmod(remainder, 60)
    parts: list[str] = []
    if days:
        parts.append(f"{days}d")
    if hours or parts:
        parts.append(f"{hours}h")
    if minutes or parts:
        parts.append(f"{minutes}m")
    parts.append(f"{secs}s")
    return " ".join(parts)


def format_bytes(value: Optional[int]) -> str:
    if value is None:
        return "n/d"
    units = ["B", "KB", "MB", "GB", "TB"]
    size = float(value)
    for unit in units:
        if size < 1024 or unit == units[-1]:
            if unit == "B":
                return f"{int(size)} {unit}"
            return f"{size:.1f} {unit}"
        size /= 1024
    return f"{size:.1f} TB"


def format_percent(value: Optional[float]) -> str:
    if value is None:
        return "n/d"
    return f"{value:.1f}%"


def safe_read_json(path: Path) -> object | None:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


@dataclass
class SuccessRecord:
    event_id: str
    timestamp: datetime
    source: str
    label: str


@dataclass
class UploadState:
    name: str
    current_item: Optional[str] = None
    current_title: Optional[str] = None
    current_path: Optional[Path] = None
    current_stage: Optional[str] = None
    progress_percent: Optional[float] = None
    confirmed_bytes: Optional[int] = None
    total_bytes: Optional[int] = None
    last_event_at: Optional[datetime] = None
    last_success_at: Optional[datetime] = None
    last_success_id: Optional[str] = None
    last_success_label: Optional[str] = None
    last_error: Optional[str] = None
    last_warning: Optional[str] = None
    last_skip_reason: Optional[str] = None
    successes: dict[str, SuccessRecord] = field(default_factory=dict)

    def register_success(self, event_id: str, timestamp: datetime, source: str, label: str) -> None:
        if event_id not in self.successes:
            self.successes[event_id] = SuccessRecord(event_id, timestamp, source, label)
        else:
            self.successes[event_id].timestamp = max(self.successes[event_id].timestamp, timestamp)
        self.last_success_at = timestamp
        self.last_success_id = event_id
        self.last_success_label = label

    def count_today(self, today: datetime) -> int:
        return sum(1 for record in self.successes.values() if record.timestamp.date() == today.date())

    def last_success_age(self, now: datetime) -> Optional[float]:
        if self.last_success_at is None:
            return None
        return (now - self.last_success_at).total_seconds()

    def activity_age(self, now: datetime) -> Optional[float]:
        if self.last_event_at is None:
            return None
        return (now - self.last_event_at).total_seconds()

    def is_active(self, now: datetime, stall_seconds: float) -> bool:
        age = self.activity_age(now)
        if age is None:
            return False
        if self.current_stage in {"done", "idle", "error", "skip"}:
            return False
        return age <= stall_seconds


class LineTracker:
    def __init__(self, path: Path):
        self.path = path
        self.offset = 0
        self.remainder = ""

    def read_new_lines(self) -> list[str]:
        if not self.path.exists():
            return []

        size = self.path.stat().st_size
        if size < self.offset:
            self.offset = 0
            self.remainder = ""

        with self.path.open("r", encoding="utf-8", errors="replace") as handle:
            handle.seek(self.offset)
            chunk = handle.read()
            self.offset = handle.tell()

        if not chunk:
            return []

        text = self.remainder + chunk
        lines = text.splitlines()
        if text.endswith(("\n", "\r")):
            self.remainder = ""
            return lines

        if lines:
            self.remainder = lines.pop()
        else:
            self.remainder = text
        return lines


class Monitor:
    def __init__(self, repo_root: Path):
        self.repo_root = repo_root
        self.meta_root = repo_root / "meta_uploader"
        self.youtube_root = repo_root / "youtube_uploader"
        self.now = datetime.now()
        self.fb = UploadState("Meta Facebook")
        self.ig = UploadState("Meta Instagram")
        self.yt = UploadState("YouTube")
        self.trackers = {
            "meta_master": LineTracker(self.meta_root / "meta_uploader.log"),
            "meta_fb": LineTracker(self.meta_root / "meta_uploader_facebook.log"),
            "meta_ig": LineTracker(self.meta_root / "meta_uploader_instagram.log"),
            "youtube": LineTracker(self.youtube_root / "uploader.log"),
        }
        self.meta_calendar = self._load_meta_calendar()
        self.youtube_index = self._load_youtube_index()
        self.meta_calendar_counts = self._summarize_meta_calendar()
        self._bootstrap()

    def _load_meta_calendar(self) -> list[dict]:
        payload = safe_read_json(self.meta_root / "meta_calendar.json")
        return payload if isinstance(payload, list) else []

    def _load_youtube_index(self) -> list[dict]:
        payload = safe_read_json(self.youtube_root / "scanned_videos.json")
        return payload if isinstance(payload, list) else []

    def _lookup_youtube_size_bytes(self) -> Optional[int]:
        current_path = self.yt.current_path
        current_item = self.yt.current_item
        filename = None
        if current_path is not None:
            filename = current_path.name
            try:
                return current_path.stat().st_size
            except OSError:
                pass
        elif current_item:
            filename = current_item

        if not filename:
            return None

        for item in self.youtube_index:
            if not isinstance(item, dict):
                continue
            candidate = item.get("filename")
            if candidate != filename:
                continue
            size_mb = item.get("size_mb")
            try:
                return int(float(size_mb) * 1024 * 1024)
            except (TypeError, ValueError):
                return None
        return None

    def _summarize_meta_calendar(self) -> tuple[int, int, int]:
        total = len(self.meta_calendar)
        scheduled = 0
        pending = 0
        for entry in self.meta_calendar:
            if not isinstance(entry, dict):
                pending += 1
                continue
            summary = entry.get("summary")
            status = summary.get("status") if isinstance(summary, dict) else None
            if isinstance(status, str) and status.startswith("scheduled"):
                scheduled += 1
            else:
                pending += 1
        return total, scheduled, pending

    def _bootstrap(self) -> None:
        for key in ("meta_master", "meta_fb", "meta_ig", "youtube"):
            tracker = self.trackers[key]
            for line in self._read_all_lines(tracker.path):
                self._ingest_line(key, line)

    @staticmethod
    def _read_all_lines(path: Path) -> list[str]:
        if not path.exists():
            return []
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except Exception:
            return []
        return text.splitlines()

    def refresh(self) -> None:
        self.now = datetime.now()
        self.meta_calendar = self._load_meta_calendar()
        self.youtube_index = self._load_youtube_index()
        self.meta_calendar_counts = self._summarize_meta_calendar()
        for key, tracker in self.trackers.items():
            for line in tracker.read_new_lines():
                self._ingest_line(key, line)

    def _parse_line(self, line: str) -> tuple[Optional[datetime], Optional[str], str]:
        match = LOG_LINE_RE.match(line)
        if not match:
            return None, None, line
        timestamp = parse_log_timestamp(match.group("ts"))
        level = match.group("level")
        msg = match.group("msg")
        return timestamp, level, msg

    def _ingest_line(self, source: str, line: str) -> None:
        timestamp, level, msg = self._parse_line(line)
        if timestamp is None:
            return

        if source.startswith("meta"):
            self._ingest_meta(timestamp, level or "INFO", msg, source)
        elif source == "youtube":
            self._ingest_youtube(timestamp, level or "INFO", msg)

    def _ingest_meta(self, timestamp: datetime, level: str, msg: str, source: str) -> None:
        if source in {"meta_master", "meta_fb"}:
            if m := FB_CHUNK_RE.search(msg):
                start = int(m.group("start"))
                total = int(m.group("total"))
                file_name = m.group("file").strip()
                self.fb.current_item = file_name
                self.fb.current_stage = "subiendo"
                self.fb.confirmed_bytes = start
                self.fb.total_bytes = total
                self.fb.progress_percent = (start / total) * 100 if total else None
                self.fb.last_event_at = timestamp
                return

            if m := FB_CONFIRM_RE.search(msg):
                confirmed = int(m.group("confirmed"))
                total = int(m.group("total"))
                file_name = m.group("file").strip()
                self.fb.current_item = file_name
                self.fb.current_stage = "subiendo"
                self.fb.confirmed_bytes = confirmed
                self.fb.total_bytes = total
                self.fb.progress_percent = (confirmed / total) * 100 if total else None
                self.fb.last_event_at = timestamp
                return

            if m := FB_SUCCESS_RE.search(msg):
                video_id = next(
                    group for group in (m.group("video_id"), m.group("video_id_alt"), m.group("video_id_pub")) if group
                )
                label = self.fb.current_item or f"video_id={video_id}"
                self.fb.register_success(video_id, timestamp, source, label)
                self.fb.current_stage = "done"
                self.fb.last_event_at = timestamp
                return

            if m := FB_EXISTING_REMOTE_RE.search(msg):
                self.fb.last_warning = f"ya existia remoto con id {m.group('video_id')}"
                self.fb.last_event_at = timestamp
                return

        if source in {"meta_master", "meta_ig"}:
            if m := IG_START_RE.search(msg):
                self.ig.current_item = m.group("item").strip()
                self.ig.current_stage = "subiendo"
                self.ig.last_event_at = timestamp
                return

            if m := IG_USING_FILE_RE.search(msg):
                self.ig.current_item = m.group("item").strip()
                self.ig.current_stage = "subiendo"
                self.ig.last_event_at = timestamp
                return

            if m := IG_TRANSCODING_RE.search(msg):
                self.ig.current_item = m.group("item").strip()
                self.ig.current_stage = "transcodificando"
                self.ig.last_event_at = timestamp
                return

            if m := IG_TRANS_DONE_RE.search(msg):
                self.ig.current_item = m.group("item").strip()
                self.ig.current_stage = "transcodificacion_ok"
                self.ig.last_event_at = timestamp
                return

            if m := IG_ACCEPT_RE.search(msg):
                media_id = m.group("media_id")
                label = self.ig.current_item or f"media_id={media_id}"
                self.ig.register_success(media_id, timestamp, source, label)
                self.ig.current_stage = "done"
                self.ig.last_event_at = timestamp
                return

            if m := IG_SKIP_RE.search(msg):
                self.ig.current_item = m.group("item").strip()
                self.ig.last_skip_reason = m.group("reason").strip()
                self.ig.current_stage = "skip"
                self.ig.last_event_at = timestamp
                return

            is_ig_error = (
                source == "meta_ig"
                or "Instagram" in msg
                or "instagram_" in msg
                or "ig_" in msg
            )
            if is_ig_error and (level == "ERROR" or "Fallo" in msg or "Error" in msg):
                self.ig.last_error = msg.strip()
                self.ig.current_stage = "error"
                self.ig.last_event_at = timestamp
                return

        if level == "WARNING":
            if "instagram_feed" in msg:
                self.ig.last_warning = msg.strip()
                self.ig.last_event_at = timestamp
                return
            if "Facebook" in msg:
                self.fb.last_warning = msg.strip()
                self.fb.last_event_at = timestamp
                return

        if level == "ERROR":
            if "Facebook" in msg or "FB" in msg:
                self.fb.last_error = msg.strip()
                self.fb.last_event_at = timestamp

    def _ingest_youtube(self, timestamp: datetime, level: str, msg: str) -> None:
        if m := YT_START_RE.match(msg):
            raw = m.group("title").strip()
            title, path = self._split_youtube_start(raw)
            self.yt.current_title = title
            self.yt.current_item = Path(path).name if path else title
            self.yt.current_path = Path(path) if path else None
            self.yt.current_stage = "subiendo"
            self.yt.last_event_at = timestamp
            self.yt.progress_percent = None
            return

        if m := YT_PROGRESS_RE.match(msg):
            self.yt.progress_percent = float(m.group("pct"))
            self.yt.current_stage = "subiendo"
            self.yt.last_event_at = timestamp
            return

        if m := YT_SUCCESS_RE.match(msg):
            video_id = m.group("video_id")
            label = self.yt.current_item or "video"
            self.yt.register_success(video_id, timestamp, "youtube", label)
            self.yt.current_stage = "done"
            self.yt.last_event_at = timestamp
            return

        if m := YT_PROGRAMMED_RE.match(msg):
            self.yt.last_event_at = timestamp
            return

        if level == "ERROR" or "quotaExceeded" in msg or "uploadLimitExceeded" in msg or "WinError" in msg:
            self.yt.last_error = msg.strip()
            self.yt.current_stage = "error"
            self.yt.last_event_at = timestamp

    @staticmethod
    def _split_youtube_start(raw: str) -> tuple[str, Optional[str]]:
        if raw.endswith(")") and " (" in raw:
            title, maybe_path = raw.rsplit(" (", 1)
            path = maybe_path[:-1]
            return title, path
        return raw, None

    def _estimate_youtube_bytes(self) -> tuple[Optional[int], Optional[int]]:
        if self.yt.progress_percent is None:
            return None, None
        total = self._lookup_youtube_size_bytes()
        if total is None:
            return None, None
        current = int(total * (self.yt.progress_percent / 100.0))
        return current, total

    def _render_section(
        self,
        title: str,
        tracker: UploadState,
        extra_lines: Iterable[str] = (),
        bytes_override: Optional[tuple[Optional[int], Optional[int]]] = None,
        show_bytes: bool = True,
    ) -> list[str]:
        now = self.now
        lines: list[str] = [title]
        active = tracker.is_active(now, stall_seconds=900)
        lines.append(f"  Estado: {'ACTIVO' if active else 'INACTIVO'}")
        if tracker.current_item:
            lines.append(f"  Video actual: {tracker.current_item}")
        if tracker.current_title and tracker.current_title != tracker.current_item:
            lines.append(f"  Titulo actual: {tracker.current_title}")
        if tracker.current_stage:
            lines.append(f"  Fase: {tracker.current_stage}")
        if tracker.progress_percent is not None:
            lines.append(f"  Progreso: {format_percent(tracker.progress_percent)}")
        if show_bytes:
            current_bytes = tracker.confirmed_bytes
            total_bytes = tracker.total_bytes
            if bytes_override is not None:
                current_bytes, total_bytes = bytes_override
            if current_bytes is not None or total_bytes is not None:
                extra = " (estimado)" if bytes_override is not None else ""
                lines.append(
                    "  Bytes: "
                    f"{format_bytes(current_bytes)} / {format_bytes(total_bytes)}"
                    f"{extra}"
                )
        lines.append(f"  Subidos hoy: {tracker.count_today(now)}")
        if tracker.last_success_at is not None:
            lines.append(
                f"  Ultima subida exitosa: {tracker.last_success_at.strftime('%Y-%m-%d %H:%M:%S')}"
                f" (hace {format_duration((now - tracker.last_success_at).total_seconds())})"
            )
        else:
            lines.append("  Ultima subida exitosa: n/d")
        if tracker.last_event_at is not None:
            lines.append(
                f"  Ultima actividad: {tracker.last_event_at.strftime('%Y-%m-%d %H:%M:%S')}"
                f" (hace {format_duration((now - tracker.last_event_at).total_seconds())})"
            )
        if tracker.last_error:
            lines.append(f"  Ultimo error: {tracker.last_error}")
        if tracker.last_warning:
            lines.append(f"  Ultimo aviso: {tracker.last_warning}")
        if tracker.last_skip_reason:
            lines.append(f"  Ultimo skip: {tracker.last_skip_reason}")
        lines.extend(extra_lines)
        return lines

    def render(self) -> str:
        fb_lines = self._render_section("META FACEBOOK", self.fb)
        ig_lines = self._render_section("META INSTAGRAM", self.ig)
        yt_bytes = self._estimate_youtube_bytes()
        yt_lines = self._render_section(
            "YOUTUBE",
            self.yt,
            bytes_override=yt_bytes,
            show_bytes=True,
        )
        header = [
            "=" * 80,
            "MONITOR EN TIEMPO REAL",
            f"Actualizado: {self.now.strftime('%Y-%m-%d %H:%M:%S')}",
            f"Raiz del repo: {self.repo_root}",
            "=" * 80,
        ]
        if self.meta_calendar:
            total, scheduled, pending = self.meta_calendar_counts
            header.append(
                f"Meta calendario: {total} dias ({scheduled} scheduled, {pending} pending)"
            )
        if self.youtube_index:
            uploaded = sum(1 for item in self.youtube_index if item.get("uploaded"))
            header.append(f"YouTube indice local: {uploaded} archivos marcados como uploaded")
        body = header + [""] + fb_lines + [""] + ig_lines + [""] + yt_lines
        return "\n".join(body)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Monitor en tiempo real de Meta y YouTube.")
    parser.add_argument("--interval", type=float, default=2.0, help="Segundos entre refrescos.")
    parser.add_argument("--once", action="store_true", help="Imprime una sola captura y sale.")
    return parser


def clear_screen() -> None:
    os.system("cls")


def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    parser = build_parser()
    args = parser.parse_args()
    repo_root = Path(__file__).resolve().parents[1]
    monitor = Monitor(repo_root)

    while True:
        monitor.refresh()
        clear_screen()
        print(monitor.render())
        if args.once:
            return 0
        time.sleep(max(0.5, args.interval))


if __name__ == "__main__":
    raise SystemExit(main())
