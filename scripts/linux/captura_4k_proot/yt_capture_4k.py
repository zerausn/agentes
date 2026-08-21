"""
yt_capture_4k.py — addon mitmproxy para el capturador 4K por navegador (S24/proot).

Captura el transporte UMP de YouTube (application/vnd.yt-ump) con separación por
epochs: cada nueva respuesta que trae init (ftyp/styp) abre una carpeta de epoch
nueva (cambio de video en playlist o cambio de calidad). Cada epoch se reensambla
después con extract_4k.py.

Variables de entorno esperadas:
  CAPTURE_SEG      - directorio base de segmentos (por epoch: <SEG>/epoch_XXXX/)
  CAPTURE_LOGS     - directorio de logs (csv global)
  PLAYBACK_RATE    - velocidad de reproduccion (ej: 0.5)
  INJECT_QUALITY   - "1" para inyectar script de seleccion de calidad
  FORCE_2160       - "1" para forzar 2160p modificando la respuesta del player
  ANDROID_CLIENT   - "1" para usar cliente Android en el player API
"""
import json
import os
import re
import time
from mitmproxy import http

SEG = os.environ.get("CAPTURE_SEG", "/sdcard/Antigravity/captura_4k/segments")
LOG_DIR = os.environ.get("CAPTURE_LOGS", "/sdcard/Antigravity/captura_4k/logs")
INJ = os.environ.get("INJECT_QUALITY", "") == "1"
RATE = os.environ.get("PLAYBACK_RATE", "") or ""
FORCE_2160 = os.environ.get("FORCE_2160", "") == "1"
ANDROID_CLIENT = os.environ.get("ANDROID_CLIENT", "") == "1"

CSV_LOG = os.path.join(LOG_DIR, "captura.csv")

RATE_SCRIPT = (b"<script>setTimeout(function(){var v=document.querySelector('video');"
               b"if(v){v.playbackRate=%s;}},4000)</script>" % RATE.encode()).strip() if RATE else b""

INJECT_SCRIPT = b"""<script>
(function () {
  function c(e) { if (e) e.click(); }
  setTimeout(function () { c(document.querySelector('.ytp-settings-button')); }, 6000);
  setTimeout(function () {
    var items = [].slice.call(document.querySelectorAll('.ytp-menuitem'));
    var q = items.find(function (x) { return /calidad|quality|resoluci/i.test(x.textContent); });
    c(q);
  }, 6400);
  setTimeout(function () {
    var o = [].slice.call(document.querySelectorAll('.ytp-menuitem-label'));
    c(o[0]);
  }, 6800);
})();
</script>"""

FORCE_QUALITY_SCRIPT = b"""<script>
(function () {
  function set2160() {
    var player = document.querySelector('#movie_player');
    if (player && player.setPlaybackQualityRange) {
      player.setPlaybackQualityRange('hd2160', 'hd2160');
      console.log('[FORCE2160] setPlaybackQualityRange called');
      return true;
    }
    if (player && player.setPlaybackQuality) {
      player.setPlaybackQuality('hd2160');
      console.log('[FORCE2160] setPlaybackQuality called');
      return true;
    }
    return false;
  }
  // Try multiple times as player may not be ready
  var attempts = 0;
  var timer = setInterval(function() {
    attempts++;
    if (set2160() || attempts >= 20) {
      clearInterval(timer);
    }
  }, 1000);
})();
</script>"""

# Minimum height to keep when FORCE_2160 is enabled
MIN_HEIGHT = 1440


class YtCapture4k:
    def __init__(self):
        self.epoch = 0
        self.n = 0
        self.cur_dir = None
        self._player_handled = set()
        os.makedirs(SEG, exist_ok=True)
        os.makedirs(LOG_DIR, exist_ok=True)
        if not os.path.exists(CSV_LOG):
            with open(CSV_LOG, "w") as f:
                f.write("ts,epoch,name,ct,start,len,status\n")

    def _epoch_dir(self):
        if self.cur_dir is None:
            self.cur_dir = os.path.join(SEG, f"epoch_{self.epoch:04d}")
            os.makedirs(self.cur_dir, exist_ok=True)
        return self.cur_dir

    def request(self, flow: http.HTTPFlow):
        """Approach 2: Switch client from WEB to ANDROID for player API."""
        if not ANDROID_CLIENT:
            return
        host = flow.request.pretty_host
        if host != "www.youtube.com" or "/youtubei/v1/player" not in flow.request.path:
            return
        if flow.request.method != "POST":
            return
        try:
            raw = flow.request.content
            if not raw:
                return
            data = json.loads(raw)
            ctx = data.get("context", {})
            client = ctx.get("client", {})
            if client.get("clientName") == "WEB":
                print(f"[ANDROID] Switching client from WEB to ANDROID for {flow.request.path}")
                ctx["client"] = {
                    "clientName": "ANDROID",
                    "clientVersion": "19.09.37",
                    "androidSdkVersion": 30,
                    "hl": "en",
                    "gl": "US",
                    "userAgent": "com.google.android.youtube/19.09.37 (Linux; U; Android 11) gzip",
                }
                data["context"] = ctx
                flow.request.content = json.dumps(data).encode()
                print(f"[ANDROID] Request body patched successfully")
        except Exception as e:
            print(f"[ANDROID] error patching request: {e}")

    def response(self, flow: http.HTTPFlow):
        host = flow.request.pretty_host
        if host == "www.youtube.com" and (
            "/watch" in flow.request.path or "/youtubei/v1/player" in flow.request.path
        ):
            try:
                body = flow.response.content or b""

                # Save to pagina.html
                if b"ytInitialPlayerResponse" in body or b"streamingData" in body:
                    with open(os.path.join(SEG, "pagina.html"), "ab") as g:
                        g.write(
                            b"<!--= " + flow.request.path.encode() + b" =-->\n" + body + b"\n"
                        )

                # Approach 1: Force 2160p by modifying streamingData in player response
                if FORCE_2160 and body and b"streamingData" in body:
                    if "/youtubei/v1/player" in flow.request.path:
                        body = self._force_quality(body)
                        flow.response.content = body
                        print(f"[FORCE2160] POST player response patched")
                    elif "/watch" in flow.request.path:
                        patched = self._force_quality_embedded(body)
                        if patched is not body:
                            flow.response.content = patched
                            body = patched
                            print(f"[FORCE2160] /watch embedded response patched")

                # Inject quality selector script (INJ mode)
                if "/watch" in flow.request.path and INJ and body and b"ytp-settings-button" not in body:
                    flow.response.content = body.replace(b"</body>", INJECT_SCRIPT + b"</body>")
                # Inject FORCE_QUALITY_SCRIPT (FORCE_2160 mode) — set quality via player API
                elif "/watch" in flow.request.path and FORCE_2160 and body and FORCE_QUALITY_SCRIPT:
                    cur = flow.response.content or body
                    flow.response.content = cur.replace(b"</body>", FORCE_QUALITY_SCRIPT + b"</body>")
                    print(f"[FORCE2160] Injected FORCE_QUALITY_SCRIPT into /watch")
                elif "/watch" in flow.request.path and RATE_SCRIPT and body:
                    flow.response.content = body.replace(b"</body>", RATE_SCRIPT + b"</body>")

            except Exception as e:
                print(f"[HTML] error {e}")

        if "googlevideo.com" not in flow.request.host:
            return
        ct = flow.response.headers.get("content-type", "")
        if not (ct.startswith("application/vnd.yt-ump") or "video" in ct or "audio" in ct):
            return
        body = flow.response.raw_content
        if not body:
            return

        if b"ftyp" in body or b"styp" in body:
            self.epoch += 1
            self.n = 0
            self.cur_dir = os.path.join(SEG, f"epoch_{self.epoch:04d}")
            os.makedirs(self.cur_dir, exist_ok=True)
            print(f"[INIT] nueva epoch {self.epoch:04d}")

        self.n += 1
        rng = flow.request.headers.get("range", "0")
        m = re.search(r"bytes=(\d+)-", rng)
        start = m.group(1) if m else "na"
        fname = f"seg_{self.n:06d}_{start}.ump"
        with open(os.path.join(self._epoch_dir(), fname), "wb") as f:
            f.write(body)
        with open(os.path.join(self._epoch_dir(), "urls.txt"), "a") as f:
            f.write(flow.request.pretty_url + "\n")
        with open(CSV_LOG, "a") as f:
            f.write(
                f"{int(time.time())},{self.epoch:04d},{fname},{ct},{start},{len(body)},{flow.response.status_code}\n"
            )
        print(f"[SAVE] e{self.epoch:04d}/{fname} ct={ct} {len(body)}B")

    def _force_quality(self, body: bytes) -> bytes:
        """Modify streamingData to keep only high-quality formats (>= MIN_HEIGHT)."""
        try:
            text = body.decode("utf-8", errors="replace")

            # Find streamingData JSON and modify adaptiveFormats
            # The response is JSON, parse it
            data = json.loads(text)
            sd = data.get("streamingData")
            if not sd:
                return body

            # Process adaptiveFormats — keep only high quality
            af = sd.get("adaptiveFormats", [])
            if af:
                before = len(af)
                high_q = [f for f in af if f.get("height", 0) >= MIN_HEIGHT]
                if high_q:
                    sd["adaptiveFormats"] = high_q
                    heights = sorted(set(f.get("height", 0) for f in high_q))
                    print(f"[FORCE2160] adaptiveFormats: {before} -> {len(high_q)} (heights: {heights})")
                else:
                    print(f"[FORCE2160] No formats >= {MIN_HEIGHT}p found, keeping all")

            # Keep formats array intact (needed for player startup)
            # Quality is forced via JavaScript injection instead

            return json.dumps(data).encode("utf-8")
        except Exception as e:
            print(f"[FORCE2160] error: {e}")
            return body

    def _force_quality_embedded(self, body: bytes) -> bytes:
        """Modify embedded ytInitialPlayerResponse in HTML to keep only high-quality formats."""
        try:
            text = body.decode("utf-8", errors="replace")
            # Find ytInitialPlayerResponse = { ... };
            pattern = r'var\s+ytInitialPlayerResponse\s*=\s*(\{)'
            match = re.search(pattern, text)
            if not match:
                # Try alternate pattern
                pattern = r'ytInitialPlayerResponse\s*=\s*(\{)'
                match = re.search(pattern, text)
            if not match:
                return body

            start = match.start(1)
            depth = 0
            for k in range(start, min(start + 2000000, len(text))):
                if text[k] == "{":
                    depth += 1
                elif text[k] == "}":
                    depth -= 1
                    if depth == 0:
                        json_str = text[start:k + 1]
                        try:
                            data = json.loads(json_str)
                            sd = data.get("streamingData")
                            if not sd:
                                return body

                            # Process adaptiveFormats
                            af = sd.get("adaptiveFormats", [])
                            if af:
                                before = len(af)
                                high_q = [f for f in af if f.get("height", 0) >= MIN_HEIGHT]
                                if high_q:
                                    sd["adaptiveFormats"] = high_q
                                    heights = sorted(set(f.get("height", 0) for f in high_q))
                                    print(f"[FORCE2160] embedded adaptiveFormats: {before} -> {len(high_q)} (heights: {heights})")
                                else:
                                    print(f"[FORCE2160] embedded: no formats >= {MIN_HEIGHT}p")

                            # Keep formats array intact (needed for player startup)
                            # Quality is forced via JavaScript injection instead

                            # Replace in HTML
                            new_json = json.dumps(data)
                            new_body = text[:start] + new_json + text[k + 1:]
                            return new_body.encode("utf-8")
                        except json.JSONDecodeError:
                            return body
                        break
            return body
        except Exception as e:
            print(f"[FORCE2160] embedded error: {e}")
            return body


addons = [YtCapture4k()]
