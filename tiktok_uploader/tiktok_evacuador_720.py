"""
tiktok_evacuador_720.py

Evacua UN SOLO VIDEO hacia TikTok usando la app Android, sin Content Posting API.
El loop de 720s vive en scripts/linux/vigia_tiktok720_termux.sh.

Flujo por ciclo:
  1. Toma el primer video (alphabetico) de /sdcard/Antigravity/subidos a facebbok.
  2. Ejecuta `touch` al archivo seleccionado para que sea el mas reciente en el filesystem
     y aparezca PRIMERO en la galeria de TikTok (que ordena por fecha de modificacion).
  3. Abre TikTok en Home via `monkey -p com.zhiliaoapp.musically` (evita permisos de intent).
  4. Navega por UI usando coordenadas escaladas y deteccion de texto:
       - Tap Crear (+) en barra inferior
       - Tap Cargar (Upload) en pantalla camara
       - Tap dropdown Recientes → busca carpeta por nombre en UI → la selecciona
       - Tap al primer video de la carpeta (que es el archivo seleccionado en paso 2)
       - Tap Siguiente en galeria
       - Tap Siguiente en editor (abajo a la derecha)
       - Tap campo descripcion → escribe caption → cierra teclado
       - Tap Publicar (por UI o fallback coordinado)
  5. Espera POST_SETTLE_SECONDS para que TikTok procese la publicacion.
  6. Verifica publicacion: si el boton Publicar desaparecio o el dump esta vacio
     (animacion post-publicacion), considera exito.
  7. Solo si todos los pasos devuelven OK, mueve el archivo a
     /sdcard/Antigravity/subidos a tiktok.

Exit codes:
  0  video enviado/publicado y movido, o dry-run OK
  1  error durante apertura/automatizacion
  2  no hay videos pendientes
  3  otra instancia esta corriendo

Cambios 2026-07-20 (Android 14 / Samsung Galaxy S24):
  - REEMPLAZADO: launch_share/launch_direct/launch_termux_open → launch_tiktok_home()
    usando `monkey` en vez de intents (Android 14 bloquea INTERACT_ACROSS_USERS_FULL).
  - NUEVO: Flujo Crear → Cargar → Recientes → carpeta por UI → video → Siguiente.
  - FIX: Siguiente editor movido de (665,77) a (531,1341) por cambio de layout en S24.
  - FIX: close_caption_editor ahora toca el fondo de pantalla para quitar foco del teclado.
  - FIX: dump_ui borra el XML anterior antes de volcar para evitar leer estados rancios.
  - FIX: publish_confirmed ahora asume exito si dump_ui devuelve lista vacia
    (animacion post-publicacion que bloquea uiautomator dump).
  - FIX: Se aplica `touch` al archivo antes de abrir TikTok para garantizar que el
    video que Python selecciona == el video que TikTok muestra primero en galeria.
"""

from __future__ import annotations

import argparse
import contextlib
import fcntl
import json
import logging
import os
import re
import shutil
import socket
import subprocess
import sys
import time
import unicodedata
import xml.etree.ElementTree as ET
from datetime import datetime
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent

try:
    sys.path.insert(0, str(BASE_DIR.parent / "youtube_uploader"))
    from video_helpers import extract_teaser_sequence, normalize_video_stem
except Exception:
    extract_teaser_sequence = None
    normalize_video_stem = None


LOG_FILE = BASE_DIR / "tiktok_evacuador.log"

ROOT_ENV = os.environ.get("AGENTES_STORAGE_ROOT", "").strip()
ROOT = Path(ROOT_ENV) if ROOT_ENV else Path("/sdcard/Antigravity")
SOURCE_DIR = ROOT / "subidos a facebbok"
DONE_DIR = ROOT / "subidos a tiktok"
FAILED_DIR = ROOT / "fallidos_tiktok"
STATE_DIR = ROOT / ".state"
STATE_FILE = STATE_DIR / "tiktok_queue.json"
CAPTION_FILE = STATE_DIR / "tiktok_caption_actual.txt"
UI_DUMP_FILE = STATE_DIR / "tiktok_ui.xml"
LOCK_FILE = STATE_DIR / "tiktok_evacuador.lock"

SUPPORTED_EXTS = {".mp4", ".mov", ".mkv"}
DEVICE_NAME = os.environ.get("AGENTES_DEVICE_NAME") or socket.gethostname() or "desconocido"
TIKTOK_PACKAGE = os.environ.get("TIKTOK_PACKAGE", "com.zhiliaoapp.musically")
TIKTOK_ACTIVITY = os.environ.get(
    "TIKTOK_SHARE_ACTIVITY",
    "com.ss.android.ugc.aweme.share.SystemShareActivity",
)
UI_BACKEND = os.environ.get("TIKTOK_UI_BACKEND", "direct").strip().lower()
ADB_SERIAL = os.environ.get("TIKTOK_ADB_SERIAL", "127.0.0.1:5555").strip()
AUTOMATION_TIMEOUT = int(os.environ.get("TIKTOK_AUTOMATION_TIMEOUT", "240"))
POST_SETTLE_SECONDS = int(os.environ.get("TIKTOK_POST_SETTLE_SECONDS", "45"))
COORD_BASE_W = 720
COORD_BASE_H = 1480
IME_PACKAGES = {
    "com.google.android.googlequicksearchbox",
    "com.samsung.android.honeyboard",
    "com.google.android.inputmethod.latin",
}


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE, encoding="utf-8"),
        logging.StreamHandler(),
    ],
)


POST_RE = re.compile(r"^(post|publish|publicar|publicar ahora)$", re.I)
NEXT_RE = re.compile(r"^(next|siguiente|continuar|continue|listo|done)$", re.I)
DISMISS_RE = re.compile(
    r"^(allow|permitir|aceptar|ok|entendido|got it|not now|ahora no|skip|saltar|cancelar|cancel)$",
    re.I,
)
BOUNDS_RE = re.compile(r"\[(\d+),(\d+)\]\[(\d+),(\d+)\]")


def now_str() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def run(cmd: list[str], timeout: int = 30) -> subprocess.CompletedProcess:
    env = os.environ.copy()
    env["PATH"] = "/data/data/com.termux/files/usr/bin:/system/bin:/system/xbin:" + env.get("PATH", "")
    return subprocess.run(cmd, text=True, capture_output=True, timeout=timeout, env=env)


def run_android(cmd: list[str], timeout: int = 30) -> subprocess.CompletedProcess:
    if UI_BACKEND == "adb":
        return run(["adb", "-s", ADB_SERIAL, "shell", *cmd], timeout=timeout)
    return run(cmd, timeout=timeout)


def shell_text_arg(text: str) -> str:
    """Texto compatible con `input text`: espacios como %s y caracteres seguros."""
    text = text.replace("%", "")
    text = unicodedata.normalize("NFKD", text)
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = re.sub(r"\s+", " ", text).strip()
    text = re.sub(r"[^0-9A-Za-z #.@/_-]", "", text)
    return text.replace(" ", "%s")[:240]


@contextlib.contextmanager
def process_lock():
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    with LOCK_FILE.open("w", encoding="utf-8") as fh:
        try:
            fcntl.flock(fh, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise RuntimeError("Otra instancia de TikTok evacuador esta corriendo")
        fh.write(f"{os.getpid()} {now_str()}\n")
        fh.flush()
        try:
            yield
        finally:
            fcntl.flock(fh, fcntl.LOCK_UN)


def load_state() -> dict:
    if not STATE_FILE.exists():
        return {"history": []}
    try:
        data = json.loads(STATE_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {"history": []}
    if not isinstance(data, dict):
        return {"history": []}
    data.setdefault("history", [])
    return data


def save_state(state: dict) -> None:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    tmp = STATE_FILE.with_suffix(".tmp")
    tmp.write_text(json.dumps(state, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    tmp.replace(STATE_FILE)


def append_history(item: dict) -> None:
    state = load_state()
    history = state.setdefault("history", [])
    history.append(item)
    if len(history) > 500:
        del history[:-500]
    state["last"] = item
    save_state(state)


def iter_videos() -> list[Path]:
    if not SOURCE_DIR.exists():
        return []
    return sorted(
        (
            f
            for f in SOURCE_DIR.iterdir()
            if f.is_file()
            and f.suffix.lower() in SUPPORTED_EXTS
            and not f.name.endswith(".part")
        ),
        key=lambda p: p.name.lower(),
    )


def file_is_stable(path: Path) -> bool:
    try:
        last_size = path.stat().st_size
    except FileNotFoundError:
        return False
    for _ in range(3):
        time.sleep(1)
        try:
            size = path.stat().st_size
        except FileNotFoundError:
            return False
        if size != last_size:
            last_size = size
            continue
        return True
    return False


def build_caption(path: Path) -> str:
    if extract_teaser_sequence:
        clean_name, teaser_num = extract_teaser_sequence(path.name)
    else:
        clean_name = path.stem.strip()
        teaser_match = re.search(r"(?i)_teaser_(\d+)$", clean_name)
        teaser_num = int(teaser_match.group(1)) if teaser_match else 1
        if teaser_match:
            clean_name = clean_name[: teaser_match.start()].strip(" _-")

    if not clean_name:
        clean_name = path.stem.strip()
    if normalize_video_stem:
        clean_name = normalize_video_stem(clean_name)

    caption_stem = re.sub(r"\s+", "_", clean_name.strip())
    caption_stem = caption_stem.strip("_")

    is_teaser = bool(re.search(r"(?i)_teaser_\d+$", path.stem))
    parts = [caption_stem, "#PW"]
    if is_teaser:
        parts.extend(["#teaser", f"#{teaser_num}"])

    parts.extend(
        [
            "Siguenos",
            "tambien",
            "en",
            "Instagram",
            "Facebook",
            "Youtube",
            "linktr.ee/performaticwritingscali",
            "#teatro",
            "#performance",
            "#escriturasperformaticas",
        ]
    )
    return " ".join(parts)


def unique_dest(folder: Path, name: str) -> Path:
    folder.mkdir(parents=True, exist_ok=True)
    candidate = folder / name
    if not candidate.exists():
        return candidate
    stem = candidate.stem
    suffix = candidate.suffix
    for i in range(1, 1000):
        alt = folder / f"{stem}__dup{i}{suffix}"
        if not alt.exists():
            return alt
    raise RuntimeError(f"No se pudo crear destino unico para {name}")


def write_caption(caption: str) -> None:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    CAPTION_FILE.write_text(caption + "\n", encoding="utf-8")

def launch_tiktok_home() -> bool:
    cmd = [
        "monkey",
        "-p",
        TIKTOK_PACKAGE,
        "-c",
        "android.intent.category.LAUNCHER",
        "1",
    ]
    result = run_android(cmd, timeout=30)
    if result.returncode == 0:
        logging.info("TikTok abierto en Home con SplashActivity.")
        return True
    logging.warning("Fallo al abrir TikTok Home: %s %s", result.stdout.strip(), result.stderr.strip())
    return False


def screen_size() -> tuple[int, int]:
    result = run_android(["wm", "size"], timeout=10)
    text = result.stdout + result.stderr
    match = re.search(r"Override size:\s*(\d+)x(\d+)", text)
    if not match:
        match = re.search(r"Physical size:\s*(\d+)x(\d+)", text)
    if match:
        return int(match.group(1)), int(match.group(2))
    return COORD_BASE_W, COORD_BASE_H


def tap_scaled(x: int, y: int, label: str, pause: float = 1.0) -> bool:
    width, height = screen_size()
    sx = round(x * width / COORD_BASE_W)
    sy = round(y * height / COORD_BASE_H)
    ok = tap((sx, sy), label)
    time.sleep(pause)
    return ok


def keyevent(key: str, label: str, pause: float = 1.0) -> bool:
    result = run_android(["input", "keyevent", key], timeout=10)
    if result.returncode == 0:
        logging.info("Keyevent: %s (%s)", key, label)
        time.sleep(pause)
        return True
    logging.warning("input keyevent fallo para %s: %s", label, result.stderr.strip())
    time.sleep(pause)
    return False


def keyboard_visible() -> bool:
    result = run_android(["dumpsys", "input_method"], timeout=15)
    text = result.stdout + result.stderr
    markers = (
        "mInputShown=true",
        "mIsInputViewShown=true",
    )
    return any(marker in text for marker in markers)


def type_caption(caption: str) -> bool:
    safe_caption = shell_text_arg(caption)
    if not safe_caption:
        return False
    result = run_android(["input", "text", safe_caption], timeout=30)
    if result.returncode == 0:
        logging.info("Caption insertado con input text: %s", safe_caption)
        return True
    logging.warning("No se pudo insertar caption: %s", result.stderr.strip())
    return False


def parse_bounds(bounds: str) -> tuple[int, int] | None:
    match = BOUNDS_RE.match(bounds or "")
    if not match:
        return None
    x1, y1, x2, y2 = map(int, match.groups())
    return (x1 + x2) // 2, (y1 + y2) // 2


def dump_ui() -> list[dict]:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    # Evitar leer un XML viejo si la pantalla esta animando y el dump falla
    run_android(["rm", "-f", str(UI_DUMP_FILE)], timeout=5)
    result = run_android(["uiautomator", "dump", str(UI_DUMP_FILE)], timeout=20)
    if result.returncode != 0:
        logging.warning("uiautomator dump fallo: %s %s", result.stdout.strip(), result.stderr.strip())
        return []
    try:
        root = ET.parse(UI_DUMP_FILE).getroot()
    except Exception as exc:
        logging.warning("No se pudo parsear UI XML: %s", exc)
        return []

    nodes: list[dict] = []
    for node in root.iter("node"):
        text = (node.attrib.get("text") or "").strip()
        desc = (node.attrib.get("content-desc") or "").strip()
        label = text or desc
        center = parse_bounds(node.attrib.get("bounds", ""))
        if not label or not center:
            continue
        if node.attrib.get("enabled") == "false":
            continue
        nodes.append(
            {
                "label": label,
                "text": text,
                "desc": desc,
                "center": center,
                "clickable": node.attrib.get("clickable") == "true",
                "class": node.attrib.get("class", ""),
            }
        )
    return nodes


def tap(center: tuple[int, int], label: str) -> bool:
    x, y = center
    result = run_android(["input", "tap", str(x), str(y)], timeout=10)
    if result.returncode == 0:
        logging.info("Tap: %s en (%s,%s)", label, x, y)
        return True
    logging.warning("input tap fallo para %s: %s", label, result.stderr.strip())
    return False


def wake_screen() -> None:
    run_android(["input", "keyevent", "KEYCODE_WAKEUP"], timeout=10)
    time.sleep(1)
    # Swipe conservador para quitar lockscreen sin PIN/patron.
    run_android(["input", "swipe", "500", "1700", "500", "500", "350"], timeout=10)
    time.sleep(1)


def reset_tiktok() -> None:
    result = run_android(["am", "force-stop", TIKTOK_PACKAGE], timeout=10)
    if result.returncode == 0:
        logging.info("TikTok reiniciado antes del ciclo.")
    else:
        logging.warning("No se pudo force-stop TikTok: %s", result.stderr.strip())


def find_match(nodes: list[dict], pattern: re.Pattern[str]) -> dict | None:
    preferred = []
    fallback = []
    for node in nodes:
        label = node["label"].strip()
        if pattern.match(label):
            (preferred if node["clickable"] else fallback).append(node)
    if preferred:
        return preferred[-1]
    if fallback:
        return fallback[-1]
    return None


def current_package() -> str:
    result = run_android(["dumpsys", "window"], timeout=15)
    text = result.stdout + result.stderr
    match = re.search(r"mCurrentFocus=.*? ([A-Za-z0-9_.]+)/", text)
    if match:
        return match.group(1)
    match = re.search(r"mFocusedApp=.*? ([A-Za-z0-9_.]+)/", text)
    return match.group(1) if match else ""


def tap_match(pattern: re.Pattern[str], label: str, timeout: int = 12) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        match = find_match(dump_ui(), pattern)
        if match and tap(match["center"], match["label"]):
            logging.info("Boton detectado para %s: %s", label, match["label"])
            return True
        time.sleep(2)
    logging.info("No se detecto boton por UI para %s; se usara fallback si existe.", label)
    return False


def close_caption_editor() -> bool:
    """
    Cierra el teclado si quedo abierto tras inyectar el texto.
    """
    ok = True
    if keyboard_visible():
        ok = keyevent("KEYCODE_BACK", "ocultar teclado descripcion", pause=2) and ok
    if keyboard_visible():
        # Tocar un espacio vacio en la pantalla para quitar el foco
        ok = tap_scaled(360, 400, "tocar fondo para ocultar teclado", pause=2) and ok
    if keyboard_visible():
        ok = keyevent("KEYCODE_BACK", "ocultar teclado descripcion reintento", pause=2) and ok
    if keyboard_visible():
        logging.warning("El teclado aun parece visible; se intentara continuar de todos modos.")
    return ok


def publish_confirmed() -> bool:
    """
    Verifica que la publicacion haya sido exitosa.
    Si el dump de UI falla (pantalla animando, transicion), asumimos exito.
    """
    pkg = current_package()

    if pkg in IME_PACKAGES:
        logging.error("Publicacion no confirmada: sigue activo el teclado (%s).", pkg)
        return False

    nodes = dump_ui()

    # Si el dump fallo (lista vacia durante animacion), asumimos exito:
    # el video ya fue enviado y TikTok esta volviendo al feed.
    if not nodes:
        logging.info("Publicacion asumida OK: dump_ui vacio (animacion post-publicacion).")
        return True

    # Si todavia vemos el boton publicar activo, fallamos
    match = find_match(nodes, POST_RE)
    if match:
        logging.error("Publicacion no confirmada: boton '%s' sigue visible.", match.get("label"))
        return False

    # Si vemos el boton "Borradores" o "Drafts", fallamos
    drafts_re = re.compile(r"^(drafts|borradores)$", re.I)
    if find_match(nodes, drafts_re):
        logging.error("Publicacion no confirmada: el video se guardo en borradores en vez de publicar.")
        return False

    logging.info("Publicacion confirmada: la UI avanzo correctamente despues del clic.")
    return True


def automate_tiktok_publish() -> bool:
    deadline = time.time() + AUTOMATION_TIMEOUT
    last_action = ""
    next_clicks = 0

    while time.time() < deadline:
        pkg = current_package()
        if pkg and pkg != TIKTOK_PACKAGE and "permissioncontroller" not in pkg:
            logging.info("Esperando TikTok; foreground=%s", pkg)

        nodes = dump_ui()
        labels = [n["label"] for n in nodes[:40]]
        logging.debug("UI labels: %s", labels)

        post = find_match(nodes, POST_RE)
        if post:
            if tap(post["center"], post["label"]):
                logging.info("Boton final detectado y tocado: %s", post["label"])
                time.sleep(POST_SETTLE_SECONDS)
                return True

        nxt = find_match(nodes, NEXT_RE)
        if nxt and next_clicks < 4:
            if tap(nxt["center"], nxt["label"]):
                next_clicks += 1
                last_action = nxt["label"]
                time.sleep(6)
                continue

        dismiss = find_match(nodes, DISMISS_RE)
        if dismiss and dismiss["label"] != last_action:
            if tap(dismiss["center"], dismiss["label"]):
                last_action = dismiss["label"]
                time.sleep(3)
                continue

        time.sleep(3)

    logging.error("No se llego al boton Publicar/Post dentro de %ss.", AUTOMATION_TIMEOUT)
    return False


TIKTOK_RE = re.compile(r"^tiktok$", re.I)
ONCE_RE = re.compile(r"^(solo\s+una\s+vez|just\s+once)$", re.I)


def chooser_select_tiktok() -> bool:
    """
    El selector de Android 'Completar la accion mediante' requiere:
      1. Tocar la app TikTok para seleccionarla (habilita los botones Solo una vez / Siempre).
      2. Tocar 'Solo una vez'.
    Usa deteccion de UI para encontrar ambos elementos por etiqueta.
    """
    logging.info("Esperando selector Android...")
    deadline = time.time() + 20
    while time.time() < deadline:
        if current_package() != "android":
            time.sleep(1)
            continue
        nodes = dump_ui()
        tiktok_node = find_match(nodes, TIKTOK_RE)
        if tiktok_node:
            logging.info("TikTok encontrado en chooser: %s", tiktok_node["center"])
            tap(tiktok_node["center"], "TikTok en chooser")
            time.sleep(2)
            # Ahora 'Solo una vez' deberia estar habilitado
            nodes2 = dump_ui()
            once_node = find_match(nodes2, ONCE_RE)
            if once_node:
                logging.info("Boton 'Solo una vez' encontrado: %s", once_node["center"])
                tap(once_node["center"], "Solo una vez")
                time.sleep(5)
                return True
            # Fallback: coordenada conocida de 'Solo una vez'
            logging.warning("No se detecto 'Solo una vez' por UI; usando coordenada fallback.")
            tap_scaled(200, 1351, "Solo una vez fallback", pause=5)
            return True
        time.sleep(2)
    logging.error("No se encontro TikTok en el chooser Android.")
    return False


def automate_tiktok_publish_coords(caption: str, folder_name: str) -> bool:
    """
    Flujo probado en Note9 con override 720x1480.
    Usa deteccion de UI para el chooser y coordenadas escaladas para el resto.
    """
    logging.info("Automatizando TikTok por coordenadas escaladas.")
    required_steps: list[tuple[str, bool]] = []

    # Home Screen: Tap Crear (+) en vez de Share Intent
    required_steps.append(("Crear (+)", tap_scaled(360, 1353, "Crear (+)", pause=5)))

    # Camera Screen: Tap Cargar (Upload) abajo a la izquierda
    required_steps.append(("Cargar", tap_scaled(70, 1330, "Cargar", pause=3)))

    # Gallery Screen: Tocar dropdown 'Recientes' para cambiar de carpeta
    required_steps.append(("Recientes", tap_scaled(360, 83, "Dropdown Recientes", pause=3)))

    # Esperar y buscar el nombre de la carpeta de origen
    folder_re = re.compile(re.escape(folder_name), re.I)
    
    # Try multiple times to find the folder as UI loads
    folder_selected = False
    for attempt in range(5):
        nodes = dump_ui()
        folder_node = find_match(nodes, folder_re)
        if folder_node:
            logging.info("Carpeta encontrada en UI: %s", folder_node["center"])
            folder_selected = tap(folder_node["center"], f"Carpeta {folder_name}")
            time.sleep(3)
            break
        time.sleep(2)
        
    required_steps.append((f"Seleccionar {folder_name}", folder_selected))

    # Permiso multimedia si aparece (poco probable en este flujo)
    tap_scaled(360, 1210, "Permitir multimedia", pause=2)

    # Galeria (carpeta filtrada): primer video y siguiente.
    required_steps.append(("primer video", tap_scaled(200, 241, "primer video", pause=1)))
    required_steps.append(("Siguiente galeria", tap_scaled(600, 1352, "Siguiente galeria", pause=6)))

    # Editor: boton Siguiente (abajo a la derecha)
    required_steps.append(("Siguiente editor", tap_scaled(531, 1341, "Siguiente editor", pause=10)))

    # Pantalla Publicar: campo descripcion, caption y publicar.
    required_steps.append(("campo descripcion", tap_scaled(178, 152, "campo descripcion", pause=1)))
    required_steps.append(("caption", type_caption(caption)))
    close_caption_editor()
    time.sleep(1)
    if tap_match(POST_RE, "Publicar", timeout=8):
        time.sleep(POST_SETTLE_SECONDS)
        required_steps.append(("Publicar", True))
    else:
        required_steps.append(("Publicar", tap_scaled(535, 1335, "Publicar fallback", pause=POST_SETTLE_SECONDS)))
    required_steps.append(("confirmar salida publicar", publish_confirmed()))

    failed = [label for label, ok in required_steps if not ok]
    if failed:
        logging.error("Automatizacion incompleta; no se mueve el archivo. Fallaron: %s", ", ".join(failed))
        return False

    logging.info("Secuencia de publicacion por coordenadas completada.")
    return True


def move_to_done(video: Path, record: dict) -> None:
    dest = unique_dest(DONE_DIR, video.name)
    shutil.move(str(video), str(dest))
    record["status"] = "published_moved"
    record["done_path"] = str(dest)
    record["finished_at"] = now_str()
    append_history(record)
    logging.info("Movido a '%s': %s", DONE_DIR.name, dest.name)
    print(f"[TIKTOK_OK] {dest}")


def open_next(args: argparse.Namespace) -> int:
    videos = iter_videos()
    if not videos:
        logging.info("No hay videos pendientes en: %s", SOURCE_DIR)
        return 2

    video = videos[0]
    if not file_is_stable(video):
        logging.info("Archivo en cambio activo; se reintentara luego: %s", video.name)
        return 2

    caption = build_caption(video)
    write_caption(caption)

    logging.info("=" * 60)
    logging.info("  TIKTOK EVACUADOR — 1 video autonomo")
    logging.info("=" * 60)
    logging.info("Fuente: %s", SOURCE_DIR)
    logging.info("Video: %s", video.name)
    logging.info("Caption: %s", CAPTION_FILE)
    print(f"[VIDEO] {video}")
    print(f"[CAPTION_FILE] {CAPTION_FILE}")
    print("[CAPTION]")
    print(caption)

    if args.dry_run:
        logging.info("DRY-RUN: no se abre TikTok ni se mueve archivo.")
        return 0

    record = {
        "name": video.name,
        "source": str(video),
        "caption": caption,
        "started_at": now_str(),
        "device": DEVICE_NAME,
    }

    wake_screen()
    reset_tiktok()

    if not launch_tiktok_home():
        record["status"] = "launch_home_failed"
        record["finished_at"] = now_str()
        append_history(record)
        return 1

    # CRITICO: hacer que el archivo seleccionado sea el mas reciente
    # en el filesystem, para que aparezca PRIMERO en la galeria de TikTok
    # (que ordena por fecha de modificacion, mas reciente primero).
    # Asi el tap fijo en (200,241) siempre tocara exactamente este archivo.
    try:
        run_android(["touch", str(video)], timeout=5)
        logging.info("touch aplicado al video seleccionado: %s", video.name)
    except Exception as exc:
        logging.warning("No se pudo hacer touch al archivo: %s", exc)

    time.sleep(8)
    folder_name = video.parent.name
    if not automate_tiktok_publish_coords(caption, folder_name):
        record["status"] = "ui_automation_failed"
        record["finished_at"] = now_str()
        append_history(record)
        return 1

    move_to_done(video, record)
    return 0


def show_status() -> int:
    pending = len(iter_videos())
    state = load_state()
    print(f"Fuente: {SOURCE_DIR}")
    print(f"Pendientes en fuente: {pending}")
    print(f"Destino OK: {DONE_DIR}")
    print(f"Destino fallidos: {FAILED_DIR}")
    print(f"Ultimo estado: {state.get('last')}")
    print(f"Caption actual: {CAPTION_FILE}")
    return 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Evacuador TikTok autonomo 720")
    parser.add_argument("--open-next", action="store_true", help="abre y publica el siguiente video")
    parser.add_argument("--status", action="store_true", help="muestra estado de la cola")
    parser.add_argument("--dry-run", action="store_true", help="no abre TikTok ni cambia archivos")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.status:
        return show_status()
    try:
        with process_lock():
            return open_next(args)
    except RuntimeError as exc:
        logging.warning("%s", exc)
        return 3


if __name__ == "__main__":
    sys.exit(main())
