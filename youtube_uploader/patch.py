import sys
import re

file_path = "/home/zerausn/Documents/Antigravity/agentes/youtube_uploader/yt_downloader_lotes_sin_limite.py"
with open(file_path, "r") as f:
    content = f.read()

# Add import at the top
if "import browser_capture" not in content:
    content = content.replace("import sys", "import sys\nimport browser_capture")

# Start mitmproxy at the very beginning of main
if "browser_capture.start_mitm()" not in content:
    content = content.replace("def main():\n    print_header()", "def main():\n    print_header()\n    browser_capture.start_mitm()")
if "browser_capture.stop_mitm()" not in content:
    content = content.replace("print(\"\\nSaliendo. ¡Hasta luego!\")\n            break", "print(\"\\nSaliendo. ¡Hasta luego!\")\n            browser_capture.stop_mitm()\n            break")

# Replace download_video yt-dlp logic
old_download_logic = """
    if not downloaded_path:
        # ── Paso 1: Descarga con yt-dlp ──────────────────────────────────────────
        log.info("  [1/2] Descargando en 4K: %s", title)
"""
new_download_logic = """
    if not downloaded_path:
        # ── Paso 1: Captura de tráfico UMP vía Chrome+mitmproxy ────────────────────────────────
        log.info("  [1/2] Capturando tráfico en 4K: %s", title)
        
        captured_file = browser_capture.capture_video(url, title)
        if not captured_file:
            log.error("Fallo la captura via browser_capture")
            return None
        
        # Copiamos el archivo al tmp de mkv/mp4 para simular el exito previo
        shutil.copy(captured_file, str(mp4_tmp))
        downloaded_path = mp4_tmp
        log.info("  Descarga OK (%.1f MB) | selector: mitmproxy_browser", downloaded_path.stat().st_size / (1024 * 1024))
        
        # Jump over all the yt-dlp code until Paso 2
        '''
"""

end_dl_logic = """
        if not downloaded_path:
            return None

    # ── Paso 2: Transcodificación a .mp4 final (si se requiere) ─────────────
"""
new_end_dl = """
        '''
        if not downloaded_path:
            return None

    # ── Paso 2: Transcodificación a .mp4 final (si se requiere) ─────────────
"""

if "browser_capture.capture_video" not in content:
    content = content.replace(old_download_logic, new_download_logic)
    content = content.replace(end_dl_logic, new_end_dl)

with open(file_path, "w") as f:
    f.write(content)
print("Patched successfully")
