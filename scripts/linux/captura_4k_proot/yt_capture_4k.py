"""
yt_capture_4k.py — addon mitmproxy para el capturador 4K por navegador (S24/proot).

Captura el transporte UMP de YouTube (application/vnd.yt-ump) con separación por
epochs: cada nueva respuesta que trae init (ftyp/styp) abre una carpeta de epoch
nueva (cambio de video en playlist o cambio de calidad). Cada epoch se reensambla
después con extract_4k.py.

Variables de entorno esperadas:
  CAPTURE_SEG  - directorio base de segmentos (por epoch: <SEG>/epoch_XXXX/)
  CAPTURE_LOGS - directorio de logs (csv global)
"""
import os
import re
import time
from mitmproxy import http

SEG = os.environ.get("CAPTURE_SEG", "/sdcard/Antigravity/captura_4k/segments")
LOG_DIR = os.environ.get("CAPTURE_LOGS", "/sdcard/Antigravity/captura_4k/logs")
INJ = os.environ.get("INJECT_QUALITY", "") == "1"

CSV_LOG = os.path.join(LOG_DIR, "captura.csv")

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


class YtCapture4k:
    def __init__(self):
        self.epoch = 0
        self.n = 0
        self.cur_dir = None
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

    def response(self, flow: http.HTTPFlow):
        host = flow.request.pretty_host
        if host == "www.youtube.com" and "/watch" in flow.request.path:
            try:
                body = flow.response.raw_content or b""
                if b"ytInitialPlayerResponse" in body:
                    with open(os.path.join(SEG, "pagina.html"), "wb") as g:
                        g.write(body)
                if INJ and body and b"ytp-settings-button" not in body:
                    flow.response.content = body.replace(b"</body>", INJECT_SCRIPT + b"</body>")
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
            f.write(f"{int(time.time())},{self.epoch:04d},{fname},{ct},{start},{len(body)},{flow.response.status_code}\n")
        print(f"[SAVE] e{self.epoch:04d}/{fname} ct={ct} {len(body)}B")


addons = [YtCapture4k()]