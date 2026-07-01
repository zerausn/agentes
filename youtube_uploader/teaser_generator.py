import functools
import json
import logging
import os
import subprocess
from pathlib import Path


BASE_DIR = Path("/data/data/com.termux/files/home/agentes/youtube_uploader")
JSON_DB = BASE_DIR / "videos_db.json"
LOG_FILE = Path("/sdcard/Antigravity/teaser_generator_debug.log")
STORAGE_ROOT = Path(os.environ.get("AGENTES_STORAGE_ROOT", "/sdcard/Antigravity"))

TEASER_DURATION_SEC = 16
FFMPEG_BIN = "/data/data/com.termux/files/usr/bin/ffmpeg"
FFPROBE_BIN = "/data/data/com.termux/files/usr/bin/ffprobe"
SEGMENT_EPSILON_SEC = 0.001


def configure_logging() -> None:
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(message)s",
        handlers=[logging.FileHandler(LOG_FILE), logging.StreamHandler()],
        force=True,
    )


@functools.lru_cache(maxsize=1)
def detect_available_encoders() -> set[str]:
    """Return set of available encoder names from this ffmpeg build (cached)."""
    try:
        result = subprocess.run(
            [FFMPEG_BIN, "-encoders"],
            capture_output=True, text=True, check=False,
        )
    except FileNotFoundError:
        return set()
    encoders: set[str] = set()
    for line in (result.stdout or "").splitlines():
        parts = line.strip().split()
        if len(parts) >= 2 and parts[0].startswith("V"):
            encoders.add(parts[1])
    return encoders


def probe_video_stream_info(input_file: Path) -> dict | None:
    """Return codec_name, pix_fmt, width, height of the first video stream."""
    command = [
        FFPROBE_BIN,
        "-v", "error",
        "-select_streams", "v:0",
        "-show_entries",
        "stream=codec_name,pix_fmt,width,height",
        "-of", "json",
        str(input_file),
    ]
    try:
        result = subprocess.run(command, capture_output=True, text=True, check=False)
    except FileNotFoundError:
        return None
    if result.returncode != 0 or not result.stdout.strip():
        return None
    try:
        data = json.loads(result.stdout)
    except json.JSONDecodeError:
        return None
    streams = data.get("streams", [])
    if not streams:
        return None
    s = streams[0]
    codec = s.get("codec_name", "")
    pix_fmt = s.get("pix_fmt", "")
    width = s.get("width", 0)
    height = s.get("height", 0)
    if not codec or not width or not height:
        return None
    return {"codec": codec, "pix_fmt": pix_fmt, "width": width, "height": height}


def build_ffmpeg_teaser_cmd(input_file: Path, start_sec: float, output_path: Path) -> list[str]:
    stream_info = probe_video_stream_info(input_file)
    can_copy = (
        stream_info
        and stream_info["codec"] == "h264"
        and stream_info["pix_fmt"] == "yuv420p"
        and stream_info["width"] % 2 == 0
        and stream_info["height"] % 2 == 0
    )
    encoders = detect_available_encoders()
    has_mediacodec = "h264_mediacodec" in encoders

    if can_copy:
        logging.info(
            "  Estrategia: stream copy (source ya es h264 yuv420p) -> %s",
            output_path.name,
        )
    elif has_mediacodec:
        logging.info(
            "  Estrategia: HW h264_mediacodec -> %s",
            output_path.name,
        )
    else:
        logging.info(
            "  Estrategia: SW libx264 (fallback) -> %s",
            output_path.name,
        )

    cmd = [
        FFMPEG_BIN,
        "-y",
        "-ss", str(round(start_sec, 3)),
        "-t", str(TEASER_DURATION_SEC),
        "-i", str(input_file),
    ]

    if can_copy:
        cmd.extend(["-c:v", "copy"])
    elif has_mediacodec:
        cmd.extend([
            "-vf", "scale=trunc(iw/2)*2:trunc(ih/2)*2,format=yuv420p",
            "-pix_fmt", "yuv420p",
            "-c:v", "h264_mediacodec",
            "-b:v", "20M",
        ])
    else:
        cmd.extend([
            "-vf", "scale=trunc(iw/2)*2:trunc(ih/2)*2,format=yuv420p",
            "-pix_fmt", "yuv420p",
            "-c:v", "libx264",
            "-crf", "18",
            "-preset", "ultrafast",
        ])

    cmd.extend([
        "-c:a", "aac",
        "-b:a", "128k",
        "-movflags", "+faststart",
        "-f", "mp4",
        str(output_path),
    ])
    return cmd


def probe_duration_seconds(input_file: Path) -> float | None:
    command = [
        FFPROBE_BIN,
        "-v",
        "error",
        "-show_entries",
        "format=duration",
        "-of",
        "default=noprint_wrappers=1:nokey=1",
        str(input_file),
    ]
    try:
        result = subprocess.run(command, capture_output=True, text=True, check=False)
    except FileNotFoundError:
        logging.error("ffprobe no encontrado en %s", FFPROBE_BIN)
        return None
    except Exception as exc:
        logging.error("No se pudo ejecutar ffprobe sobre %s: %s", input_file.name, exc)
        return None

    if result.returncode != 0:
        logging.error("ffprobe fallo para %s", input_file.name)
        logging.error("  STDOUT: %s", result.stdout)
        logging.error("  STDERR: %s", result.stderr)
        return None

    raw_duration = (result.stdout or "").strip()
    try:
        duration_sec = float(raw_duration)
    except ValueError:
        logging.error("ffprobe devolvio una duracion invalida para %s: %r", input_file.name, raw_duration)
        return None

    if duration_sec <= 0:
        logging.error("Duracion no valida para %s: %.6f", input_file.name, duration_sec)
        return None
    return duration_sec


def build_segment_starts(duration_sec: float) -> list[float]:
    segment_starts = []
    start_sec = 0.0
    while start_sec + TEASER_DURATION_SEC <= duration_sec + SEGMENT_EPSILON_SEC:
        segment_starts.append(round(start_sec, 3))
        start_sec += TEASER_DURATION_SEC
    if not segment_starts and duration_sec > 0:
        segment_starts = [0.0]
    return segment_starts


def expected_outputs_for(output_dir: Path, base_name: str, duration_sec: float) -> list[Path]:
    return [
        output_dir / f"{base_name}_teaser_{index}.mp4"
        for index, _start_sec in enumerate(build_segment_starts(duration_sec), start=1)
    ]


def main() -> None:
    configure_logging()
    logging.info("=" * 60)
    logging.info(" INICIANDO GENERADOR DE TEASERS (CORTES DE 16 SEG)")
    logging.info("=" * 60)

    input_dir = STORAGE_ROOT / "crudos_pendientes"
    output_dir = STORAGE_ROOT / "teasers_pendientes"
    markers_dir = STORAGE_ROOT / ".state"
    output_dir.mkdir(exist_ok=True, parents=True)
    markers_dir.mkdir(exist_ok=True, parents=True)

    files = list(input_dir.glob("*.mp4"))
    if not files:
        logging.info("No se encontraron videos en %s", input_dir)
        return

    for input_file in files:
        base_name = input_file.stem
        logging.info("Generando teasers para: %s", input_file.name)

        duration_sec = probe_duration_seconds(input_file)
        if duration_sec is None:
            logging.error("  Saltando %s: no se pudo determinar la duracion real", input_file.name)
            continue

        segment_starts = build_segment_starts(duration_sec)
        if not segment_starts:
            logging.warning(
                "  Saltando %s: la duracion %.3fs no alcanza para generar teasers",
                input_file.name,
                duration_sec,
            )
            continue

        logging.info(
            "Video: %s | Duracion: %.1fs | Partes de %ss -> %s segmentos totales",
            input_file.name,
            duration_sec,
            TEASER_DURATION_SEC,
            len(segment_starts),
        )

        done_marker = markers_dir / f"{base_name}.done"
        lock_marker = markers_dir / f"{base_name}.lock"
        expected_outputs = expected_outputs_for(output_dir, base_name, duration_sec)
        missing_outputs = [path for path in expected_outputs if not path.exists()]

        if done_marker.exists():
            if not missing_outputs:
                logging.info(
                    "  Ignorando %s porque ya existe marker .done y estan los %s teasers esperados",
                    input_file.name,
                    len(expected_outputs),
                )
                continue
            logging.warning(
                "  Marker .done huerfano detectado para %s: faltan %s teaser(s). Se regenerara.",
                input_file.name,
                len(missing_outputs),
            )
            done_marker.unlink(missing_ok=True)

        if lock_marker.exists():
            logging.info(
                "  Ignorando %s porque ya existe marker .lock (otro proceso)",
                input_file.name,
            )
            continue

        try:
            lock_marker.write_text(str(os.getpid()), encoding="utf-8")
            failed_segments: list[int] = []

            for index, start_sec in enumerate(segment_starts, start=1):
                final_output = output_dir / f"{base_name}_teaser_{index}.mp4"
                if final_output.exists():
                    logging.info(
                        "  Saltando segmento %s porque ya existe: %s",
                        index,
                        final_output.name,
                    )
                    continue

                temp_output = Path(str(final_output) + ".part")
                command = build_ffmpeg_teaser_cmd(input_file, start_sec, temp_output)
                segment_end_sec = min(start_sec + TEASER_DURATION_SEC, duration_sec)

                result = subprocess.run(command, capture_output=True, text=True)
                if result.returncode == 0:
                    try:
                        os.replace(str(temp_output), str(final_output))
                        logging.info(
                            "  [OK] Parte %s/%s -> %s (s%s - s%s)",
                            index,
                            len(segment_starts),
                            final_output.name,
                            round(start_sec),
                            round(segment_end_sec),
                        )
                    except Exception as exc:
                        failed_segments.append(index)
                        logging.error(
                            "  [FAIL] Parte %s/%s no se pudo cerrar como %s: %s",
                            index,
                            len(segment_starts),
                            final_output,
                            exc,
                        )
                        temp_output.unlink(missing_ok=True)
                else:
                    failed_segments.append(index)
                    logging.error(
                        "  [FAIL] Parte %s/%s -> %s (s%s - s%s)",
                        index,
                        len(segment_starts),
                        final_output.name,
                        round(start_sec),
                        round(segment_end_sec),
                    )
                    logging.error("  STDOUT: %s", result.stdout)
                    logging.error("  STDERR: %s", result.stderr)
                    temp_output.unlink(missing_ok=True)

            missing_outputs = [path for path in expected_outputs if not path.exists()]
            if missing_outputs or failed_segments:
                done_marker.unlink(missing_ok=True)
                logging.error(
                    "  No se crea marker .done para %s. Faltan %s teaser(s): %s",
                    input_file.name,
                    len(missing_outputs),
                    ", ".join(path.name for path in missing_outputs) if missing_outputs else "ninguno",
                )
            else:
                done_marker.write_text("ok", encoding="utf-8")
                logging.info("  Marca de procesado creada: %s", done_marker.name)
        finally:
            lock_marker.unlink(missing_ok=True)

    logging.info(
        "Proceso finalizado. Puedes revisar los archivos en %s",
        output_dir,
    )


if __name__ == "__main__":
    main()
