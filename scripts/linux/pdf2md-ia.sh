#!/bin/bash
# pdf2md-ia.sh - Pipeline PDF → Markdown pulido para IA (Parrot/Debian, CPU 30%, Intel Iris Xe)
# Uso: ./pdf2md-ia.sh libro.pdf [salida.md]
# Requiere: pymupdf4llm (pipx), marker-env (~/marker-env), ollama opcional
set -e
PDF="$1"
OUT="${2:-${PDF%.pdf}-LIMPIO.md}"
if [ -z "$PDF" ]; then echo "Uso: $0 <pdf> [salida.md]"; exit 1; fi
export OMP_NUM_THREADS=4 MKL_NUM_THREADS=4 OPENBLAS_NUM_THREADS=4
export LD_LIBRARY_PATH=/home/zerausn/.local/bin:$LD_LIBRARY_PATH
TMPMD=$(mktemp /tmp/pdf2md_XXXX.md)
echo "[1/3] Convirtiendo $PDF con pymupdf4llm (OCR, lotes 5 pág)..."
# Si es >50 pág, hacerlo por lotes para no timeout
python3 << PY
import pymupdf4llm
from pathlib import Path
import time
pdf="$PDF"
out="$TMPMD"
pages=len(__import__("pymupdf").open(pdf))
print(f"Páginas: {pages}")
Path(out).write_text("")
batch=5
start=time.time()
for i in range(0, pages, batch):
    ps=list(range(i, min(i+batch, pages)))
    print(f"[{ps[0]+1}-{ps[-1]+1}/{pages}]...")
    md=pymupdf4llm.to_markdown(pdf, pages=ps)
    Path(out).write_text(Path(out).read_text(encoding="utf-8") + f"\n\n{md}", encoding="utf-8")
print(f"Listo {time.time()-start:.1f}s -> {out} {Path(out).stat().st_size/1024:.1f}KB")
PY
echo "[2/3] Limpiando watermarks, headers, <br>, guiones..."
python3 << PY
import re
from pathlib import Path
p=Path("$TMPMD")
t=p.read_text(encoding="utf-8")
# Watermarks
for pat in [r"EBSCO.*?Lewis,\n?", r"EBSCOhost.*?All use subject to\n?", r"https://www\.ebsco\.com/terms-of-use\.\n?", r"Córdoba Padilla, M\. \(2011\).*?page=\d+ *\n?", r"Copyright © 2011.*?\n?", r"https://elibro-net.*?\n"]:
    t=re.sub(pat,"",t,flags=re.DOTALL)
# Tablas <br>
t=re.sub(r"(\w+)-<br>(\w+)",r"\1\2",t)
t=re.sub(r"<br\s*/?>"," ",t)
# Concatenadas
for k,v in {"Sernuevoenelmercado.":"Ser nuevo en el mercado.", "Adquirirnuevastecnologias,":"Adquirir nuevas tecnologias,","FORMULACIONY":"FORMULACION Y","ESTUDIODEFACTIBILIDAD":"ESTUDIO DE FACTIBILIDAD"}.items():
    t=t.replace(k,v)
t=re.sub(r"(\w+)-\s*\n\s*(\w+)",r"\1\2",t)
t=re.sub(r"\n{3,}","\n\n",t)
t=t.strip()
Path("$OUT").write_text(t,encoding="utf-8")
print(f"Limpio -> $OUT {len(t)} chars")
PY
echo "[3/3] Listo: $OUT"
ls -lh "$OUT"
