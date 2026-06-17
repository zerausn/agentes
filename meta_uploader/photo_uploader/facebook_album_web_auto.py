#!/usr/bin/env python3
import argparse
import json
import os
import re
import shlex
import shutil
import subprocess
import sys
import time
import uuid
from collections import Counter
from pathlib import Path
from urllib.error import URLError
from urllib.request import urlopen

import requests
import websocket


SCRIPT_DIR = Path(__file__).resolve().parent
META_DIR = SCRIPT_DIR.parent
DESKTOP_DIR = Path.home() / "Desktop"

PHOTO_DIR = Path("/media/zerausn/D69493CF9493B08B/Users/ZN-/Documents/ADM/Carpeta 1/Fotos")
ENV_PATH = META_DIR / ".env"
MISSING_OUT = DESKTOP_DIR / "albumes_faltantes_facebook.txt"
ALL_OUT = DESKTOP_DIR / "albumes_por_fecha_detectados.txt"
PROGRESS_OUT = DESKTOP_DIR / "albumes_creados_web_progress.json"
PLACEHOLDER = Path("/tmp/facebook_album_placeholder.jpg")
GRAPH = "https://graph.facebook.com/v19.0"
SUPPORTED = {".jpg", ".jpeg", ".png", ".webp", ".dng"}
DIR_PROCESADAS = Path("/media/zerausn/D69493CF9493B08B/Users/ZN-/Documents/ADM/Carpeta 1/fotos_subidas_album")
HISTORIAL_FILE = SCRIPT_DIR / "album_diario_historial.json"
SEEDS_OUT = DESKTOP_DIR / "albumes_seed_web.json"
SINGLE_PHOTO_ALBUM_NAME = "Fotos sueltas"


def load_env(path):
    vals = {}
    if not path.exists():
        return vals
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        vals[key.strip()] = value.strip().strip('"').strip("'")
    return vals


def extract_date(stem):
    match = re.match(r"(\d{8})", stem)
    if not match:
        return None
    raw = match.group(1)
    return f"{raw[:4]}-{raw[4:6]}-{raw[6:8]}"


def local_album_counts():
    counts = Counter()
    for path in sorted(PHOTO_DIR.iterdir(), key=lambda item: item.name):
        if not path.is_file() or path.suffix.lower() not in SUPPORTED:
            continue
        date = extract_date(path.stem)
        if date:
            counts[date] += 1
    return counts


def local_album_files():
    counts = local_album_counts()
    files = {}
    for path in sorted(PHOTO_DIR.iterdir(), key=lambda item: item.name):
        if not path.is_file() or path.suffix.lower() not in SUPPORTED:
            continue
        date = extract_date(path.stem)
        if date:
            album_name = SINGLE_PHOTO_ALBUM_NAME if counts[date] == 1 else f"Fotos {date}"
            files.setdefault(album_name, []).append(path)
    return files


def graph_get(path, token, params=None):
    payload = dict(params or {})
    payload["access_token"] = token
    try:
        response = requests.get(f"{GRAPH}/{path}", params=payload, timeout=60)
        return response.json()
    except requests.RequestException as exc:
        return {"error": {"message": f"network_error:{exc.__class__.__name__}", "type": "LocalNetworkError"}}


def list_remote_albums(page_id, token):
    url_base = f"{GRAPH}/{page_id}/albums"
    for intento in range(1, 4):
        url = url_base
        params = {"access_token": token, "limit": "100", "fields": "id,name,count,created_time,link"}
        albums = {}
        try:
            while url:
                response = requests.get(url, params=params if "?" not in url else {}, timeout=60)
                body = response.json()
                if "error" in body:
                    print(f"ERROR leyendo albumes remotos (intento {intento}/3): {safe_error(body['error'])}", file=sys.stderr)
                    break
                for album in body.get("data", []):
                    name = album.get("name", "")
                    if name:
                        albums[name] = album
                url = body.get("paging", {}).get("next")
                params = {}
            if albums:
                return albums
            else:
                print(f"ADVERTENCIA: Lectura de albumes vacia (intento {intento}/3).", file=sys.stderr)
        except requests.RequestException as exc:
            print(f"ERROR leyendo albumes remotos (intento {intento}/3): network_error:{exc.__class__.__name__}", file=sys.stderr)
        time.sleep(3 * intento)
    return {}


def safe_error(error):
    return {key: error.get(key) for key in ["message", "type", "code", "error_subcode", "fbtrace_id"] if key in error}


def write_album_lists(counts, remote):
    expected = []
    all_lines = []
    single_count = sum(1 for count in counts.values() if count == 1)
    if single_count:
        expected.append(SINGLE_PHOTO_ALBUM_NAME)
        all_lines.append(f"{SINGLE_PHOTO_ALBUM_NAME}\t{single_count} fotos sueltas")
    for date in sorted(counts):
        if counts[date] > 1:
            name = f"Fotos {date}"
            expected.append(name)
            all_lines.append(f"{name}\t{counts[date]} fotos")
    missing = [name for name in expected if name not in remote]
    missing_lines = []
    for name in missing:
        if name == SINGLE_PHOTO_ALBUM_NAME:
            missing_lines.append(f"{name}\t{single_count} fotos sueltas")
        else:
            missing_lines.append(f"{name}\t{counts[name.removeprefix('Fotos ')]} fotos")
    ALL_OUT.write_text("\n".join(all_lines) + ("\n" if all_lines else ""), encoding="utf-8")
    MISSING_OUT.write_text("\n".join(missing_lines) + ("\n" if missing_lines else ""), encoding="utf-8")
    return expected, missing


class Cdp:
    def __init__(self, ws_url):
        self.ws = websocket.create_connection(ws_url, timeout=30)
        self.seq = 0

    def call(self, method, params=None):
        self.seq += 1
        message_id = self.seq
        self.ws.send(json.dumps({"id": message_id, "method": method, "params": params or {}}))
        while True:
            payload = json.loads(self.ws.recv())
            if payload.get("id") == message_id:
                if "error" in payload:
                    raise RuntimeError(f"{method}: {payload['error']}")
                return payload.get("result", {})

    def eval(self, expression, await_promise=True):
        result = self.call(
            "Runtime.evaluate",
            {
                "expression": expression,
                "awaitPromise": await_promise,
                "returnByValue": True,
                "userGesture": True,
            },
        )
        value = result.get("result", {})
        return value.get("value")

    def close(self):
        try:
            self.ws.close()
        except Exception:
            pass


def http_json(url):
    with urlopen(url, timeout=2) as response:
        return json.loads(response.read().decode("utf-8"))


def wait_debugger(port, timeout=30):
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            return http_json(f"http://127.0.0.1:{port}/json/version")
        except (URLError, TimeoutError, OSError):
            time.sleep(0.5)
    raise RuntimeError("No pude conectar al puerto remoto del navegador.")


def new_tab(port, url):
    endpoint = f"http://127.0.0.1:{port}/json/new?{url}"
    response = requests.put(endpoint, timeout=10)
    return response.json()


def command_exists(command):
    try:
        path = subprocess.check_output(["bash", "-lc", f"command -v {shlex.quote(command)} || true"], text=True).strip()
    except subprocess.SubprocessError:
        path = ""
    return path


def edge_flatpak_available():
    try:
        subprocess.check_call(["flatpak", "info", "com.microsoft.Edge"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return True
    except (FileNotFoundError, subprocess.SubprocessError):
        return False


def edge_flatpak_running():
    try:
        output = subprocess.check_output(["bash", "-lc", "pgrep -af 'com.microsoft.Edge|/app/extra/msedge|/app/bin/edge' || true"], text=True)
    except subprocess.SubprocessError:
        output = ""
    return bool(output.strip())


def browser_command(preferred):
    if preferred:
        if preferred in {"edge", "msedge", "microsoft-edge", "microsoft-edge-stable"} and edge_flatpak_available():
            return ["flatpak", "run", "com.microsoft.Edge"], "edge-flatpak"
        parts = shlex.split(preferred)
        if len(parts) > 1:
            return parts, "custom"
        path = command_exists(preferred)
        if path:
            return [path], "custom"

    if edge_flatpak_available():
        return ["flatpak", "run", "com.microsoft.Edge"], "edge-flatpak"

    candidates = ["microsoft-edge", "microsoft-edge-stable", "google-chrome", "chromium", "chromium-browser"]
    for candidate in candidates:
        path = command_exists(candidate)
        if path:
            return [path], candidate
    raise RuntimeError("No encontre Edge/Chrome/Chromium instalado.")


def launch_browser(command, kind, port, page_url, restart_edge):
    try:
        wait_debugger(port, timeout=1)
        if not (kind == "edge-flatpak" and restart_edge and edge_flatpak_running()):
            return None
    except RuntimeError:
        pass

    if kind == "edge-flatpak" and edge_flatpak_running():
        if not restart_edge:
            raise RuntimeError(
                "Edge esta abierto pero no tiene DevTools activo. Ejecuta con --restart-edge para reiniciarlo automaticamente."
            )
        print("Edge esta abierto sin DevTools; lo reinicio para poder automatizar albumes.")
        subprocess.call(["flatpak", "kill", "com.microsoft.Edge"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        time.sleep(4)

    profile_dir = os.environ.get("FB_ALBUM_BROWSER_PROFILE", str(Path.home() / ".config/google-chrome"))
    args = list(command) + [
        f"--remote-debugging-port={port}",
        "--remote-allow-origins=*",
        "--no-first-run",
        "--new-window",
        page_url,
    ]
    if profile_dir and kind != "edge-flatpak":
        args.insert(1, f"--user-data-dir={profile_dir}")
    return subprocess.Popen(args, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def create_placeholder(album_name=None):
    album_files = local_album_files()
    candidates = [
        path for path in album_files.get(album_name, [])
        if path.suffix.lower() in {".jpg", ".jpeg", ".png", ".webp"}
    ]
    if not candidates:
        candidates = [
            path
            for path in PHOTO_DIR.iterdir()
            if path.is_file() and path.suffix.lower() in {".jpg", ".jpeg", ".png", ".webp"}
        ]
    if not candidates:
        raise RuntimeError("No hay una foto real para usar como semilla temporal del album.")
    seed_dir = Path.home() / "Downloads"
    seed_dir.mkdir(parents=True, exist_ok=True)
    last_error = None
    for source in sorted(candidates, key=lambda item: item.stat().st_size):
        seed = seed_dir / f"facebook_album_seed_{source.stem}.jpg"
        try:
            if seed.exists():
                seed.unlink()
            make_seed_image(source, seed)
            return seed, source
        except Exception as exc:
            last_error = exc
            if seed.exists():
                seed.unlink()
    raise RuntimeError(f"No pude crear una semilla web reducida: {last_error}")


def make_seed_image(source, seed):
    from PIL import Image, ImageFile, ImageOps

    ImageFile.LOAD_TRUNCATED_IMAGES = True
    Image.MAX_IMAGE_PIXELS = None
    with Image.open(source) as image:
        image = ImageOps.exif_transpose(image)
        image = image.convert("RGB")
        side = min(image.width, image.height)
        if side < 10:
            raise RuntimeError(f"imagen invalida: {source.name}")
        left = (image.width - side) // 2
        top = (image.height - side) // 2
        image = image.crop((left, top, left + side, top + side))
        resampling = getattr(getattr(Image, "Resampling", Image), "LANCZOS")
        image = image.resize((1200, 1200), resampling)
        image.save(seed, "JPEG", quality=88, optimize=True)

    if not seed.exists() or seed.stat().st_size < 1024:
        raise RuntimeError(f"semilla invalida: {seed}")


def load_json(path):
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def save_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def archive_seed_photo(album_name, album_id, seed_source):
    if not seed_source or not seed_source.exists():
        return
    DIR_PROCESADAS.mkdir(parents=True, exist_ok=True)
    album_dir = DIR_PROCESADAS / album_name
    album_dir.mkdir(parents=True, exist_ok=True)
    destino_album = album_dir / seed_source.name
    shutil.copy2(seed_source, destino_album)

    destino_legacy = DIR_PROCESADAS / seed_source.name
    if not destino_legacy.exists():
        shutil.move(str(seed_source), str(destino_legacy))
    else:
        seed_source.unlink()

    historial = load_json(HISTORIAL_FILE)
    historial[seed_source.stem] = {
        "album": album_name,
        "album_id": album_id,
        "subido": time.strftime("%Y-%m-%d %H:%M:%S"),
        "via": "facebook_web_seed",
    }
    save_json(HISTORIAL_FILE, historial)

    seeds = load_json(SEEDS_OUT)
    seeds[album_name] = {
        "album_id": album_id,
        "seed_file": seed_source.name,
        "archived_to": str(destino_album),
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
    }
    save_json(SEEDS_OUT, seeds)


def js_literal(value):
    return json.dumps(value, ensure_ascii=False)


JS_HELPERS = r"""
(() => {
  window.__ag = window.__ag || {};
  window.__ag.visible = (el) => {
    if (!el) return false;
    const style = getComputedStyle(el);
    const rect = el.getBoundingClientRect();
    return style.visibility !== 'hidden' && style.display !== 'none' && rect.width > 0 && rect.height > 0;
  };
  window.__ag.text = (el) => ((el.getAttribute('aria-label') || '') + ' ' + (el.innerText || el.textContent || '')).trim();
  window.__ag.clickText = (texts) => {
    const lower = texts.map(t => t.toLowerCase());
    const nodes = Array.from(document.querySelectorAll('[role="button"], button, a, div[aria-label], span[aria-label]'))
      .filter(window.__ag.visible);
    for (const node of nodes) {
      const text = window.__ag.text(node).toLowerCase();
      if (lower.some(target => text.includes(target))) {
        node.scrollIntoView({block: 'center', inline: 'center'});
        node.click();
        return {ok: true, text: window.__ag.text(node)};
      }
    }
    return {ok: false};
  };
  window.__ag.clickPublish = () => {
    const nodes = Array.from(document.querySelectorAll('[role="button"], button'))
      .filter(window.__ag.visible)
      .filter(node => /Publicar|Post/i.test(window.__ag.text(node)))
      .filter(node => node.getAttribute('aria-disabled') !== 'true' && node.disabled !== true);
    if (!nodes.length) return {ok: false, reason: 'publish_not_found_or_disabled'};
    const node = nodes[nodes.length - 1];
    node.scrollIntoView({block: 'center', inline: 'center'});
    node.focus();
    for (const type of ['pointerdown', 'mousedown', 'pointerup', 'mouseup', 'click']) {
      node.dispatchEvent(new MouseEvent(type, {bubbles: true, cancelable: true, view: window}));
    }
    return {ok: true, text: window.__ag.text(node)};
  };
  window.__ag.setAlbumName = (name) => {
    const candidates = Array.from(document.querySelectorAll('input[type="text"], textarea, [contenteditable="true"]'))
      .filter(window.__ag.visible)
      .filter(el => (el.getAttribute('type') || '').toLowerCase() !== 'search');
    const preferred = candidates.find(el => {
      const label = window.__ag.text(el).toLowerCase() + ' ' + (el.getAttribute('placeholder') || '').toLowerCase();
      return label.includes('album') || label.includes('álbum') || label.includes('nombre') || label.includes('title') || label.includes('título');
    }) || candidates[candidates.length - 1];
    if (!preferred) return {ok: false, count: candidates.length};
    preferred.scrollIntoView({block: 'center', inline: 'center'});
    preferred.focus();
    if (preferred.isContentEditable) {
      preferred.textContent = name;
    } else {
      const setter = Object.getOwnPropertyDescriptor(preferred.tagName === 'TEXTAREA' ? HTMLTextAreaElement.prototype : HTMLInputElement.prototype, 'value').set;
      setter.call(preferred, name);
    }
    preferred.dispatchEvent(new InputEvent('input', {bubbles: true, inputType: 'insertText', data: name}));
    preferred.dispatchEvent(new Event('change', {bubbles: true}));
    return {ok: true, tag: preferred.tagName, label: window.__ag.text(preferred)};
  };
  window.__ag.hasLogin = () => {
    const body = (document.body.innerText || '').toLowerCase();
    return !(body.includes('log in') || body.includes('iniciar sesión') || body.includes('iniciar sesion'));
  };
  return true;
})()
"""


def cdp_attach_file(cdp, file_path):
    cdp.call("DOM.enable")
    root = cdp.call("DOM.getDocument", {"depth": -1, "pierce": True})["root"]["nodeId"]
    node = cdp.call("DOM.querySelector", {"nodeId": root, "selector": "input[type=file]"})["nodeId"]
    if not node:
        return False
    cdp.call("DOM.setFileInputFiles", {"nodeId": node, "files": [str(file_path)]})
    return True


def wait_publish_ready(cdp, timeout=300):
    deadline = time.time() + timeout
    while time.time() < deadline:
        state = cdp.eval(
            r"""
            (() => {
              const visible = el => { const s=getComputedStyle(el); const r=el.getBoundingClientRect(); return s.display!='none' && s.visibility!='hidden' && r.width>0 && r.height>0; };
              const text = el => ((el.getAttribute('aria-label')||'')+' '+(el.innerText||el.textContent||'')).trim();
              const body = document.body.innerText || '';
              const publish = [...document.querySelectorAll('[role="button"],button')]
                .filter(visible)
                .find(el => /Publicar|Post|Create|Crear/i.test(text(el)));
              return JSON.stringify({
                hasError: /Error al subir|No se puede subir|upload failed|cannot upload/i.test(body),
                publishVisible: !!publish,
                publishDisabled: publish ? (publish.getAttribute('aria-disabled') === 'true' || publish.disabled === true) : true
              });
            })()
            """
        )
        parsed = json.loads(state)
        if parsed.get("hasError"):
            raise RuntimeError("Facebook marco error al subir la semilla temporal.")
        if parsed.get("publishVisible") and not parsed.get("publishDisabled"):
            return True
        time.sleep(2)
    raise RuntimeError("Facebook no habilito Publicar despues de subir la semilla temporal.")


def wait_remote_album(name, page_id, token, timeout=300, min_count=None):
    deadline = time.time() + timeout
    while time.time() < deadline:
        albums = list_remote_albums(page_id, token)
        if name in albums:
            album = albums[name]
            if min_count is None or int(album.get("count") or 0) >= min_count:
                return album
        time.sleep(5)
    return None


def delete_album_placeholder_photos(album_id, token):
    body = graph_get(album_id + "/photos", token, {"fields": "id,created_time,name", "limit": "25"})
    if "error" in body:
        print(f"WARNING: no pude listar placeholder del album {album_id}: {safe_error(body['error'])}")
        return
    for photo in body.get("data", []):
        photo_id = photo.get("id")
        if not photo_id:
            continue
        response = requests.delete(f"{GRAPH}/{photo_id}", params={"access_token": token}, timeout=30)
        result = response.json()
        if "error" in result:
            print(f"WARNING: no pude borrar placeholder {photo_id}: {safe_error(result['error'])}")
        else:
            print(f"Placeholder borrado: {photo_id}")


def create_album_web(cdp, name, page_id, token, allow_placeholder):
    cdp.call("Page.navigate", {"url": "https://www.facebook.com/media/set/create/"})
    time.sleep(6)
    cdp.eval(JS_HELPERS)
    if not cdp.eval("window.__ag.hasLogin()"):
        raise RuntimeError("Facebook no esta logueado en este perfil del navegador.")

    cdp.eval(JS_HELPERS)
    set_result = cdp.eval(f"window.__ag.setAlbumName({js_literal(name)})")
    if not set_result or not set_result.get("ok"):
        raise RuntimeError("No pude llenar el nombre del album.")

    if allow_placeholder:
        placeholder_path, seed_source = create_placeholder(name)
        print(f"Semilla web: {seed_source.name}")
        attached = cdp_attach_file(cdp, placeholder_path)
        if attached:
            wait_publish_ready(cdp)
            cdp.eval(JS_HELPERS)
            cdp.eval(f"window.__ag.setAlbumName({js_literal(name)})")
    else:
        seed_source = None

    post_result = cdp.eval("window.__ag.clickPublish()")
    if not post_result or not post_result.get("ok"):
        raise RuntimeError(f"No pude pulsar Publicar: {post_result}")

    print(f"Publicar pulsado: {post_result.get('text')}. Esperando confirmacion Graph...")
    album = wait_remote_album(name, page_id, token, timeout=300, min_count=1 if allow_placeholder else None)
    if not album:
        raise RuntimeError("Facebook no confirmo el album por Graph API.")
    print(f"Confirmado por Facebook Graph: album_id={album.get('id')} fotos={album.get('count', 0)}")
    if allow_placeholder and seed_source:
        if placeholder_path.exists():
            placeholder_path.unlink()
        seeds = load_json(SEEDS_OUT)
        seeds[name] = {
            "album_id": album["id"],
            "seed_source": str(seed_source),
            "seed_note": "Semilla web reducida para crear el album; copia temporal eliminada, original se sube despues por API.",
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        }
        save_json(SEEDS_OUT, seeds)
    return album


def run(args):
    env = load_env(ENV_PATH)
    page_id = env.get("META_FB_PAGE_ID", "")
    token = env.get("META_FB_PAGE_TOKEN", "")
    if not page_id or not token:
        raise RuntimeError("Faltan META_FB_PAGE_ID o META_FB_PAGE_TOKEN.")

    counts = local_album_counts()
    remote = list_remote_albums(page_id, token)
    _, missing = write_album_lists(counts, remote)
    print(f"Fechas detectadas: {len(counts)}")
    print(f"Albumes remotos existentes: {len(remote)}")
    print(f"Albumes faltantes: {len(missing)}")
    print(f"Lista faltantes: {MISSING_OUT}")
    if not missing:
        return 0

    if args.dry_run:
        return 0

    if args.limit and args.limit > 0:
        missing = missing[:args.limit]

    browser, browser_kind = browser_command(args.browser)
    page_url = f"https://www.facebook.com/profile.php?id={page_id}&sk=photos_albums"
    process = launch_browser(browser, browser_kind, args.port, page_url, args.restart_edge)
    version = wait_debugger(args.port, timeout=30)
    tab = new_tab(args.port, page_url)
    ws_url = tab.get("webSocketDebuggerUrl") or version.get("webSocketDebuggerUrl")
    if not ws_url:
        raise RuntimeError("No pude obtener websocket de Chrome DevTools.")

    progress = {"created": [], "failed": []}
    limited_run = bool(args.limit and args.limit > 0)
    cdp = Cdp(ws_url)
    try:
        cdp.call("Page.enable")
        cdp.call("Runtime.enable")
        for index, name in enumerate(missing, start=1):
            print(f"[{index}/{len(missing)}] creando album web: {name}")
            try:
                album = create_album_web(cdp, name, page_id, token, args.placeholder)
                print(f"OK: {name} -> {album.get('id')}")
                progress["created"].append({"name": name, "id": album.get("id")})
            except Exception as exc:
                print(f"ERROR: {name}: {exc}")
                progress["failed"].append({"name": name, "error": str(exc)})
                if not args.continue_on_error:
                    break
            PROGRESS_OUT.write_text(json.dumps(progress, indent=2, ensure_ascii=False), encoding="utf-8")
    finally:
        cdp.close()

    remote = list_remote_albums(page_id, token)
    _, missing_after = write_album_lists(counts, remote)
    print(f"Albumes faltantes despues: {len(missing_after)}")
    if limited_run:
        return 0 if not progress["failed"] else 2
    return 0 if not missing_after else 2


def main():
    parser = argparse.ArgumentParser(description="Crear albumes de Facebook automaticamente por navegador.")
    parser.add_argument("--browser", default=os.environ.get("FB_ALBUM_BROWSER", "edge"), help="Navegador. Default: edge. Acepta edge, google-chrome o comando completo.")
    parser.add_argument("--port", type=int, default=int(os.environ.get("FB_ALBUM_DEBUG_PORT", "9222")))
    parser.add_argument("--placeholder", action="store_true", help="Sube una imagen placeholder si Facebook exige foto para crear album.")
    parser.add_argument("--restart-edge", action="store_true", help="Si Edge ya esta abierto sin DevTools, lo cierra y lo reabre con automatizacion.")
    parser.add_argument("--continue-on-error", action="store_true", help="Sigue con el siguiente album si uno falla.")
    parser.add_argument("--dry-run", action="store_true", help="Solo genera la lista; no abre navegador ni crea albumes.")
    parser.add_argument("--limit", type=int, default=0, help="Limita cuantos albumes crear en esta corrida.")
    args = parser.parse_args()
    try:
        raise SystemExit(run(args))
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(1)


if __name__ == "__main__":
    main()
