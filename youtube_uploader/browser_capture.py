"""
browser_capture.py — Captura de video 4K vía Firefox+mitmproxy (motor UMP) usando CDP clásico.
Sigue el flujo documentado para el PC.

Addons:
  - yt_capture.py: addon avanzado con separación por epochs (detección ftyp/styp),
    organización en epoch_XXXX/, inyección PLAYBACK_RATE.
  - yt_ump_extract.py: reensambla los epochs en .mp4 AV1/VP9.

Flujo:
  1. mitmdump con yt_capture.py captura UMP → segments/
  2. Firefox con proxy al puerto 8080 y remote-debugging-port 9222.
  3. cdp_4k.py: se conecta a :9222/json, hace play + 2160p60 via DOM.
  4. Monitor de segments/ hasta 150s sin datos.
  5. yt_ump_extract.py reensambla epochs → MP4.
"""
import os
import sys
import time
import subprocess

MITM_VENV   = os.path.expanduser("~/venv-mitm")
CAP_BASE    = "/mnt/Videos/yt_browser_capture"
SEG_DIR     = f"{CAP_BASE}/segments"
OUT_DIR     = f"{CAP_BASE}/salidas"
ADDON_PY    = f"{CAP_BASE}/yt_capture.py"
EXTRACT_PY  = f"{CAP_BASE}/yt_ump_extract.py"
CDP_PY      = f"{CAP_BASE}/cdp_4k.py"
LOG_MITM    = f"{CAP_BASE}/logs/mitmdump.log"
LOG_FIREFOX = f"{CAP_BASE}/logs/firefox.log"

# ── 1. Lanzar mitmdump con el addon ──────────────────
def start_mitm():
    subprocess.run(["pkill", "-f", "venv-mitm/bin/mitmdump"], stderr=subprocess.DEVNULL)
    time.sleep(1)
    os.makedirs(f"{CAP_BASE}/logs", exist_ok=True)

    env = os.environ.copy()
    env["CAPTURE_SEG"]  = SEG_DIR
    env["CAPTURE_LOGS"] = f"{CAP_BASE}/logs"
    env["PLAYBACK_RATE"] = "0.5"

    cmd = [
        f"{MITM_VENV}/bin/mitmdump", "-q",
        "-s", ADDON_PY,
        "--listen-host", "127.0.0.1",
        "--listen-port", "8080",
    ]
    with open(LOG_MITM, "w") as f:
        p = subprocess.Popen(cmd, env=env, stdout=f, stderr=subprocess.STDOUT)
    time.sleep(3)

    r = subprocess.run(["ss", "-tln"], capture_output=True, text=True)
    if ":8080" not in r.stdout:
        print("  [ERROR] mitmdump NO quedó escuchando en :8080")
        return None
    print(f"  [MITM] mitmdump activo con yt_capture.py (PID {p.pid})")
    return p

def stop_mitm():
    subprocess.run(["pkill", "-f", "venv-mitm/bin/mitmdump"], stderr=subprocess.DEVNULL)

# ── 2. Capturar un video ──────────────────────────────────────────────────────
def capture_video(url: str, title: str) -> str | None:
    """
    Captura el video en URL usando Firefox + CDP. 
    Devuelve ruta del .mp4 final, o None si falló.
    """
    print(f"\n  [BROWSER] Iniciando captura: {title}")

    # Limpiar workspace
    os.makedirs(SEG_DIR, exist_ok=True)
    os.makedirs(OUT_DIR, exist_ok=True)
    for item in os.listdir(SEG_DIR):
        item_path = os.path.join(SEG_DIR, item)
        if os.path.isdir(item_path):
            import shutil; shutil.rmtree(item_path)
        else:
            os.remove(item_path)

    # ── Lanzar Firefox con proxy y remote-debugging ──
    # Es obligatorio que el perfil configurado en Firefox confíe en mitmproxy-ca-cert.pem
    # y tenga la pref "remote.active-protocols=2" para soportar CDP /json en FF 128+
    env = os.environ.copy()
    env["DISPLAY"] = ":0"
    
    firefox_cmd = [
        "firefox",
        "--proxy-server=http://127.0.0.1:8080",
        "--remote-debugging-port=9222",
        "--remote-allow-origins=*",
        "--autoplay-policy=no-user-gesture-required",
        url,
    ]
    with open(LOG_FIREFOX, "w") as f:
        ff_proc = subprocess.Popen(firefox_cmd, env=env, stdout=f, stderr=subprocess.STDOUT)
    
    print(f"  [BROWSER] Firefox PID {ff_proc.pid} en DISPLAY=:0")
    time.sleep(15)  # carga inicial

    # ── CDP: play + seleccionar 2160p60 en el menú de calidad ────────────────
    print("  [CDP] Forzando play + calidad 2160p60...")
    try:
        r = subprocess.run(
            [f"{MITM_VENV}/bin/python", CDP_PY],
            cwd=CAP_BASE,
            capture_output=True, text=True, timeout=90,
        )
        for line in r.stdout.strip().splitlines():
            print(f"  [CDP] {line}")
        if r.returncode != 0 and r.stderr:
            print(f"  [CDP] error: {r.stderr[:200]}")
    except Exception as e:
        print(f"  [CDP] falló: {e}")
        ff_proc.kill()
        return None

    # ── Monitor: esperar fin de reproducción (150s sin datos nuevos) ──────────
    last_sz = 0
    last_seen = time.time()
    media_started = False
    deadline = time.time() + 7200

    while time.time() < deadline:
        time.sleep(15)
        try:
            result = subprocess.check_output(["du", "-sb", SEG_DIR])
            sz = int(result.decode().split()[0])
        except Exception:
            sz = 0

        if sz > last_sz:
            last_seen = time.time()
        last_sz = sz

        if not media_started and sz > 0:
            media_started = True

        if media_started and (time.time() - last_seen) > 150:
            print(f"\n  [CAPTURE] Fin detectado. Total capturado: {sz/1024/1024:.1f} MB")
            break

        sys.stdout.write(f"\r  [UMP] Capturando... {sz/1024/1024:.1f} MB   ")
        sys.stdout.flush()

    # Matar Firefox
    ff_proc.terminate()
    time.sleep(2)
    ff_proc.kill()
    subprocess.run(["pkill", "-f", "firefox"], stderr=subprocess.DEVNULL)
    print()

    if not media_started:
        print("  [ERROR] No se capturó ningún segmento. Verificar proxy y Firefox.")
        return None

    # ── Extracción con yt_ump_extract.py ──────────────────────────────────────────
    print("  [EXTRACT] Reensamblando epochs → MP4...")
    try:
        r = subprocess.run(
            [f"{MITM_VENV}/bin/python", EXTRACT_PY],
            capture_output=True, text=True, timeout=180,
            cwd=CAP_BASE
        )
        for line in r.stdout.strip().splitlines():
            print(f"  [EXTRACT] {line}")
        if r.returncode != 0:
            print(f"  [EXTRACT] stderr: {r.stderr[:300]}")
    except Exception as e:
        print(f"  [EXTRACT] error: {e}")
        return None

    # El MP4 es salidas/video_capturado.mp4
    best = os.path.join(OUT_DIR, "video_capturado.mp4")

    if not os.path.exists(best) or os.path.getsize(best) == 0:
        print("  [ERROR] No se generó ningún .mp4 válido en salidas/")
        return None

    print(f"  [OK] MP4 final: {best} ({os.path.getsize(best)/1024/1024:.1f} MB)")
    return best
