import argparse
import json
import math
import subprocess
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent
EXPERIMENT_ROOT = BASE_DIR / "outputs" / "yolo_reframe_experiments"
PLAN_DIR = EXPERIMENT_ROOT / "plans"
RENDER_DIR = EXPERIMENT_ROOT / "renders"


def run_command(command):
    return subprocess.run(command, capture_output=True, text=True, check=False)


def probe_video(video_path):
    cmd = [
        "ffprobe",
        "-v",
        "error",
        "-show_entries",
        "format=duration,size:stream=index,codec_type,width,height,r_frame_rate",
        "-of",
        "json",
        str(video_path),
    ]
    result = run_command(cmd)
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or f"ffprobe fallo para {video_path}")
    payload = json.loads(result.stdout)
    streams = payload.get("streams") or []
    video_stream = next((s for s in streams if s.get("codec_type") == "video"), {})
    fmt = payload.get("format") or {}
    fps_raw = str(video_stream.get("r_frame_rate") or "30/1")
    if "/" in fps_raw:
        left, right = fps_raw.split("/", 1)
        fps = float(left) / float(right or 1)
    else:
        fps = float(fps_raw or 30)
    return {
        "duration": float(fmt.get("duration") or 0.0),
        "size_bytes": int(fmt.get("size") or 0),
        "width": int(video_stream.get("width") or 0),
        "height": int(video_stream.get("height") or 0),
        "fps": fps or 30.0,
    }


def require_runtime_dependencies():
    try:
        import cv2  # noqa: F401
    except ImportError as exc:
        raise RuntimeError(
            "Falta OpenCV. Instala opencv-python o ejecuta esta herramienta en un entorno que ya lo tenga."
        ) from exc

    try:
        from ultralytics import YOLO  # noqa: F401
    except ImportError as exc:
        raise RuntimeError(
            "Falta ultralytics/YOLOv8. Instala `ultralytics` antes de usar esta herramienta experimental."
        ) from exc


def pick_segment(video_meta, start_seconds=None, duration_seconds=None):
    total_duration = float(video_meta["duration"])
    start = max(0.0, float(start_seconds or 0.0))
    remaining = max(0.0, total_duration - start)
    if remaining <= 0:
        raise ValueError("El segmento queda fuera del rango del video.")
    duration = float(duration_seconds or min(remaining, 30.0))
    duration = min(duration, remaining)
    if duration <= 0:
        raise ValueError("La duracion del segmento debe ser mayor que cero.")
    return round(start, 2), round(duration, 2)


def apply_composition_rule(center_x, crop_width, source_width, composition_rule):
    if composition_rule == "golden_ratio":
        center_x -= int(crop_width * 0.118)
    elif composition_rule == "thirds":
        center_x -= int(crop_width * (1 / 3 - 0.5))
    half = crop_width // 2
    left = max(0, min(source_width - crop_width, center_x - half))
    return left


def detect_subject_center(results, source_width):
    boxes = getattr(results[0], "boxes", None)
    if boxes is None or len(boxes) == 0:
        return source_width // 2, False

    best_center = source_width // 2
    best_area = 0.0
    for box in boxes:
        x1, y1, x2, y2 = box.xyxy[0].tolist()
        area = max(0.0, (x2 - x1) * (y2 - y1))
        if area > best_area:
            best_area = area
            best_center = int((x1 + x2) / 2)
    return best_center, True


def build_crop_plan(
    video_path,
    *,
    start_seconds,
    duration_seconds,
    output_width,
    output_height,
    sample_every_frames,
    tracking_smoothing,
    composition_rule,
    yolo_model,
):
    require_runtime_dependencies()
    import cv2
    from ultralytics import YOLO

    video_meta = probe_video(video_path)
    source_width = int(video_meta["width"])
    source_height = int(video_meta["height"])
    fps = float(video_meta["fps"] or 30.0)
    crop_width = min(source_width, int(source_height * output_width / output_height))
    crop_height = source_height

    cap = cv2.VideoCapture(str(video_path))
    cap.set(cv2.CAP_PROP_POS_MSEC, start_seconds * 1000)
    model = YOLO(yolo_model)

    frame_index = 0
    sampled = 0
    detections = 0
    total_frames = max(1, int(math.ceil(duration_seconds * fps)))
    detected_center = source_width // 2
    smoothed_center = detected_center
    alpha = max(0.0, min(1.0, 1.0 - tracking_smoothing))
    plan_points = []

    while frame_index < total_frames:
        ok, frame = cap.read()
        if not ok:
            break

        if frame_index % sample_every_frames == 0:
            results = model(frame, classes=[0], verbose=False)
            detected_center, found = detect_subject_center(results, source_width)
            sampled += 1
            detections += 1 if found else 0
            smoothed_center = int(alpha * detected_center + (1.0 - alpha) * smoothed_center)
            crop_left = apply_composition_rule(smoothed_center, crop_width, source_width, composition_rule)
            timestamp = round(start_seconds + (frame_index / fps), 3)
            plan_points.append(
                {
                    "time_seconds": timestamp,
                    "center_x": smoothed_center,
                    "crop_left": crop_left,
                    "crop_width": crop_width,
                    "detected": bool(found),
                }
            )

        frame_index += 1

    cap.release()

    return {
        "video_path": str(video_path),
        "segment": {
            "start_seconds": start_seconds,
            "duration_seconds": duration_seconds,
        },
        "source_meta": video_meta,
        "output_meta": {
            "width": output_width,
            "height": output_height,
            "crop_width": crop_width,
            "crop_height": crop_height,
            "composition_rule": composition_rule,
            "tracking_smoothing": tracking_smoothing,
            "sample_every_frames": sample_every_frames,
            "yolo_model": yolo_model,
        },
        "summary": {
            "sampled_points": sampled,
            "detections": detections,
            "detection_rate": round(detections / sampled, 3) if sampled else 0.0,
        },
        "plan_points": plan_points,
    }


def save_plan(plan, video_path, start_seconds, duration_seconds):
    PLAN_DIR.mkdir(parents=True, exist_ok=True)
    output_name = f"{Path(video_path).stem}__{start_seconds:.2f}s__{duration_seconds:.2f}s__yolo_plan.json"
    output_path = PLAN_DIR / output_name
    with open(output_path, "w", encoding="utf-8") as handle:
        json.dump(plan, handle, indent=2, ensure_ascii=False)
    return output_path


def render_plan(plan, output_path):
    require_runtime_dependencies()
    import cv2

    source_path = Path(plan["video_path"])
    start_seconds = float(plan["segment"]["start_seconds"])
    duration_seconds = float(plan["segment"]["duration_seconds"])
    output_width = int(plan["output_meta"]["width"])
    output_height = int(plan["output_meta"]["height"])
    crop_width = int(plan["output_meta"]["crop_width"])
    fps = float(plan["source_meta"]["fps"] or 30.0)
    total_frames = max(1, int(math.ceil(duration_seconds * fps)))

    point_index = 0
    plan_points = plan["plan_points"]
    if not plan_points:
        raise RuntimeError("El plan no contiene puntos de crop.")

    cap = cv2.VideoCapture(str(source_path))
    cap.set(cv2.CAP_PROP_POS_MSEC, start_seconds * 1000)

    tmp_output = output_path.with_suffix(".tmp.mp4")
    writer = cv2.VideoWriter(
        str(tmp_output),
        cv2.VideoWriter_fourcc(*"mp4v"),
        fps,
        (output_width, output_height),
    )

    for frame_index in range(total_frames):
        ok, frame = cap.read()
        if not ok:
            break

        current_time = start_seconds + (frame_index / fps)
        while point_index + 1 < len(plan_points) and plan_points[point_index + 1]["time_seconds"] <= current_time:
            point_index += 1

        crop_left = int(plan_points[point_index]["crop_left"])
        crop_right = crop_left + crop_width
        cropped = frame[:, crop_left:crop_right]
        resized = cv2.resize(cropped, (output_width, output_height), interpolation=cv2.INTER_LANCZOS4)
        writer.write(resized)

    cap.release()
    writer.release()
    mux_audio(source_path, tmp_output, output_path, start_seconds, duration_seconds)
    tmp_output.unlink(missing_ok=True)
    return output_path


def mux_audio(source_path, temp_video_path, output_path, start_seconds, duration_seconds):
    command = [
        "ffmpeg",
        "-y",
        "-i",
        str(temp_video_path),
        "-ss",
        str(start_seconds),
        "-t",
        str(duration_seconds),
        "-i",
        str(source_path),
        "-map",
        "0:v:0",
        "-map",
        "1:a:0",
        "-c:v",
        "libx264",
        "-preset",
        "fast",
        "-crf",
        "18",
        "-c:a",
        "aac",
        "-b:a",
        "192k",
        "-shortest",
        "-movflags",
        "+faststart",
        str(output_path),
    ]
    result = run_command(command)
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or "Fallo ffmpeg al reinyectar audio.")


def main():
    parser = argparse.ArgumentParser(
        description="Herramienta experimental separada para probar reencuadre YOLO 9:16 sin integrarlo al flujo productivo."
    )
    parser.add_argument("--input", required=True, help="Ruta al video fuente.")
    parser.add_argument("--start-seconds", type=float, default=0.0)
    parser.add_argument("--duration-seconds", type=float, default=30.0)
    parser.add_argument("--output-width", type=int, default=1080)
    parser.add_argument("--output-height", type=int, default=1920)
    parser.add_argument("--sample-every-frames", type=int, default=5)
    parser.add_argument("--tracking-smoothing", type=float, default=0.85)
    parser.add_argument(
        "--composition-rule",
        choices=["center", "golden_ratio", "thirds"],
        default="golden_ratio",
    )
    parser.add_argument("--yolo-model", default="yolov8n.pt")
    parser.add_argument(
        "--render",
        action="store_true",
        help="Ademas del plan JSON, renderiza un clip vertical experimental.",
    )
    args = parser.parse_args()

    video_path = Path(args.input).resolve()
    if not video_path.exists():
        raise FileNotFoundError(f"No existe el archivo {video_path}")

    video_meta = probe_video(video_path)
    start_seconds, duration_seconds = pick_segment(
        video_meta,
        start_seconds=args.start_seconds,
        duration_seconds=args.duration_seconds,
    )

    plan = build_crop_plan(
        video_path,
        start_seconds=start_seconds,
        duration_seconds=duration_seconds,
        output_width=args.output_width,
        output_height=args.output_height,
        sample_every_frames=max(1, args.sample_every_frames),
        tracking_smoothing=args.tracking_smoothing,
        composition_rule=args.composition_rule,
        yolo_model=args.yolo_model,
    )
    plan_path = save_plan(plan, video_path, start_seconds, duration_seconds)
    print(f"Plan experimental guardado en: {plan_path}")
    print(f"Puntos muestreados: {plan['summary']['sampled_points']}")
    print(f"Detecciones YOLO: {plan['summary']['detections']}")
    print(f"Tasa de deteccion: {plan['summary']['detection_rate']}")

    if args.render:
        RENDER_DIR.mkdir(parents=True, exist_ok=True)
        output_name = f"{video_path.stem}__{start_seconds:.2f}s__{duration_seconds:.2f}s__yolo_vertical.mp4"
        output_path = RENDER_DIR / output_name
        render_plan(plan, output_path)
        print(f"Render experimental guardado en: {output_path}")


if __name__ == "__main__":
    main()
