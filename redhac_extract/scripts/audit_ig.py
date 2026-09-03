"""
audit_ig.py — Auditoría completa de los 469 posts de Instagram REDHAC.

Compara ig_full_data.json (scrapeado) contra ig_469.json (fuente original de URLs)
y clasifica cada post según la calidad de sus datos.

Salidas:
  output/ig_audit_report.md   → Reporte legible con estadísticas y lista de problemas
  output/ig_rescrape_list.json → Lista de shortcodes que necesitan re-extracción
  output/ig_relikers_list.json → Lista de shortcodes que solo necesitan re-likers (API)

Uso:
  python3 scripts/audit_ig.py
"""

import json
import unicodedata
from pathlib import Path
from datetime import datetime

# ── Rutas ─────────────────────────────────────────────────────────────────────
FULL_JSON     = Path(__file__).parent.parent / "output" / "ig_full_data.json"
IG_469_PATH   = Path("/media/zerausn/D69493CF9493B08B/Users/ZN-/Documents/UNAD/"
                     "CURSOS/6/METODOLOGÍA Y GESTIÓN DE LA INVESTIGACIÓN/1/"
                     "Documentacion/1/ig_469.json")
OUT_DIR       = Path(__file__).parent.parent / "output"
REPORT_PATH   = OUT_DIR / "ig_audit_report.md"
RESCRAPE_PATH = OUT_DIR / "ig_rescrape_list.json"
RELIKERS_PATH = OUT_DIR / "ig_relikers_list.json"


def has_emoji(text: str) -> bool:
    """Detecta si un texto contiene emojis o caracteres Unicode especiales."""
    for c in text:
        cat = unicodedata.category(c)
        cp = ord(c)
        if cat in ("So", "Sm") or (0x1F300 <= cp <= 0x1FAFF) or (0x2600 <= cp <= 0x27BF):
            return True
    return False


def classify_post(code: str, data: dict) -> dict:
    """Clasifica un post y retorna un dict con sus métricas de calidad."""
    issues = []
    flags = {}

    if data.get("error"):
        return {"code": code, "status": "ERROR", "issues": ["error_scraping"], "flags": {}}

    href       = data.get("href", "")
    texto      = data.get("texto", "") or ""
    likes      = data.get("likes")
    likers     = data.get("likers") or []
    nro_com    = data.get("nro_comentarios")
    comentarios = data.get("comentarios") or []
    fecha      = data.get("fecha") or ""
    menciones  = data.get("menciones") or []
    imgs       = data.get("imgs") or []
    vids       = data.get("vids") or []

    # ── Checks de likers ──────────────────────────────────────────────────────
    flags["n_likers"] = len(likers)
    if not likers:
        issues.append("sin_likers")
    elif likes and len(likers) < int(likes or 0) * 0.5 and int(likes or 0) > 20:
        # Tenemos likers pero son menos del 50% del total de likes reportado
        issues.append("likers_incompletos")

    # ── Checks de likes count ─────────────────────────────────────────────────
    flags["likes"] = likes
    if likes is None:
        issues.append("sin_likes_count")
    elif int(likes or 0) <= 4 and len(likers) > 10:
        issues.append("likes_sospechosos")  # El count es bajo pero hay muchos likers

    # ── Checks de comentarios ─────────────────────────────────────────────────
    flags["nro_comentarios"] = nro_com
    flags["n_comentarios_capturados"] = len(comentarios)
    if nro_com and int(nro_com or 0) > 0 and not comentarios:
        issues.append("sin_comentarios")
    elif nro_com and int(nro_com or 0) > 0 and comentarios:
        ratio = len(comentarios) / int(nro_com)
        if ratio < 0.5 and int(nro_com) > 5:
            issues.append("comentarios_incompletos")

    # ── Checks de emojis en comentarios ──────────────────────────────────────
    flags["emojis_en_comentarios"] = False
    for cm in comentarios:
        if has_emoji(cm):
            flags["emojis_en_comentarios"] = True
            break

    # ── Checks de texto ───────────────────────────────────────────────────────
    if not texto or len(texto) < 10:
        issues.append("sin_texto")
    elif has_emoji(texto):
        flags["emojis_en_texto"] = True

    # ── Checks de fecha ───────────────────────────────────────────────────────
    if not fecha:
        issues.append("sin_fecha")

    # ── Checks de medios ─────────────────────────────────────────────────────
    flags["n_imgs"] = len(imgs)
    flags["n_vids"] = len(vids)
    if not imgs and not vids:
        issues.append("sin_media")

    # ── Status general ────────────────────────────────────────────────────────
    critical = {"sin_likers", "sin_comentarios", "sin_likes_count", "sin_texto"}
    moderate = {"likers_incompletos", "comentarios_incompletos", "sin_fecha", "likes_sospechosos"}

    if any(i in critical for i in issues):
        status = "CRITICO"
    elif any(i in moderate for i in issues):
        status = "INCOMPLETO"
    elif issues:
        status = "MENOR"
    else:
        status = "OK"

    return {
        "code": code,
        "href": href,
        "status": status,
        "issues": issues,
        "flags": flags,
    }


def main():
    print("=== Auditoría ig_full_data.json ===\n")

    if not FULL_JSON.exists():
        print(f"❌ No existe {FULL_JSON}")
        print("   Ejecuta primero: python3 scripts/scrape_ig_full.py")
        return

    full_data = json.loads(FULL_JSON.read_text(encoding="utf-8"))

    # Cargar la fuente original para verificar que están todos
    src_codes = set()
    if IG_469_PATH.exists():
        raw = json.loads(IG_469_PATH.read_text(encoding="utf-8"))
        media = raw.get("media", raw) if isinstance(raw, dict) else raw
        for m in media:
            href = m.get("href", "")
            code = href.rstrip("/").split("/")[-1]
            src_codes.add(code)
        print(f"Posts en ig_469.json (fuente):    {len(src_codes)}")
    else:
        print(f"⚠️  No se encontró ig_469.json en disco externo — verificando solo ig_full_data.json")

    print(f"Posts en ig_full_data.json:        {len(full_data)}")

    # ── Clasificar cada post ──────────────────────────────────────────────────
    results = []
    for code, data in full_data.items():
        r = classify_post(code, data)
        results.append(r)

    # ── Contadores ────────────────────────────────────────────────────────────
    by_status = {"OK": [], "INCOMPLETO": [], "CRITICO": [], "ERROR": []}
    by_issue  = {}
    for r in results:
        by_status[r["status"]].append(r["code"])
        for issue in r["issues"]:
            by_issue.setdefault(issue, []).append(r["code"])

    total = len(results)

    print(f"\n{'='*55}")
    print(f"  RESULTADOS DE AUDITORÍA — {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print(f"{'='*55}")
    print(f"  ✅ OK (completos):         {len(by_status['OK']):>4}  ({len(by_status['OK'])/total*100:.1f}%)")
    print(f"  🟡 INCOMPLETO:             {len(by_status['INCOMPLETO']):>4}  ({len(by_status['INCOMPLETO'])/total*100:.1f}%)")
    print(f"  🔴 CRÍTICO:                {len(by_status['CRITICO']):>4}  ({len(by_status['CRITICO'])/total*100:.1f}%)")
    print(f"  ❌ ERROR (scraping):       {len(by_status['ERROR']):>4}  ({len(by_status['ERROR'])/total*100:.1f}%)")
    print(f"{'='*55}")
    print(f"\n  Desglose por problema:")
    for issue, codes in sorted(by_issue.items(), key=lambda x: -len(x[1])):
        print(f"  • {issue:<35} {len(codes):>4} posts")

    # Emojis en comentarios
    n_emoji_com = sum(1 for r in results if r["flags"].get("emojis_en_comentarios"))
    n_emoji_txt = sum(1 for r in results if r["flags"].get("emojis_en_texto"))
    print(f"\n  Emojis detectados en texto:          {n_emoji_txt:>4}")
    print(f"  Emojis detectados en comentarios:    {n_emoji_com:>4}  ← debe ser > 0 con v2")

    # ── Listas de acción ─────────────────────────────────────────────────────
    # Re-scraping completo: posts críticos o con error
    rescrape = [r["code"] for r in results
                if r["status"] in ("CRITICO", "ERROR")
                or "sin_texto" in r.get("issues", [])
                or "sin_fecha" in r.get("issues", [])]

    # Solo re-likers: tienen texto y fecha pero les faltan likers
    relikers = [r["code"] for r in results
                if r["status"] not in ("ERROR",)
                and ("sin_likers" in r.get("issues", []) or "likers_incompletos" in r.get("issues", []))
                and "sin_texto" not in r.get("issues", [])
                and r["code"] not in rescrape]

    print(f"\n  Acción requerida:")
    print(f"  • Re-scraping completo:   {len(rescrape):>4} posts")
    print(f"  • Solo re-likers (API):   {len(relikers):>4} posts")
    print(f"  • Sin acción necesaria:   {len(results) - len(rescrape) - len(relikers):>4} posts")

    # ── Guardar listas ────────────────────────────────────────────────────────
    OUT_DIR.mkdir(exist_ok=True)

    RESCRAPE_PATH.write_text(
        json.dumps({"total": len(rescrape), "codes": rescrape}, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )
    RELIKERS_PATH.write_text(
        json.dumps({"total": len(relikers), "codes": relikers}, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )

    # ── Generar reporte Markdown ──────────────────────────────────────────────
    lines = [
        f"# Auditoría Instagram REDHAC — {datetime.now().strftime('%Y-%m-%d %H:%M')}\n\n",
        f"## Resumen\n\n",
        f"| Estado | Posts | % |\n",
        f"|---|---|---|\n",
        f"| ✅ OK | {len(by_status['OK'])} | {len(by_status['OK'])/total*100:.1f}% |\n",
        f"| 🟡 Incompleto | {len(by_status['INCOMPLETO'])} | {len(by_status['INCOMPLETO'])/total*100:.1f}% |\n",
        f"| 🔴 Crítico | {len(by_status['CRITICO'])} | {len(by_status['CRITICO'])/total*100:.1f}% |\n",
        f"| ❌ Error | {len(by_status['ERROR'])} | {len(by_status['ERROR'])/total*100:.1f}% |\n\n",
        f"## Problemas Detectados\n\n",
        f"| Problema | Posts afectados |\n",
        f"|---|---|\n",
    ]
    for issue, codes in sorted(by_issue.items(), key=lambda x: -len(x[1])):
        lines.append(f"| `{issue}` | {len(codes)} |\n")

    lines += [
        f"\n## Emojis\n\n",
        f"- Emojis en texto del post: **{n_emoji_txt}** posts\n",
        f"- Emojis en comentarios: **{n_emoji_com}** posts\n\n",
        f"## Acción Requerida\n\n",
        f"- Re-scraping completo (`ig_rescrape_list.json`): **{len(rescrape)} posts**\n",
        f"- Solo re-likers API (`ig_relikers_list.json`): **{len(relikers)} posts**\n\n",
        f"## Posts por Status\n\n",
    ]

    for status, codes in by_status.items():
        if codes:
            lines.append(f"### {status} ({len(codes)})\n")
            for c in codes[:20]:
                p = full_data.get(c, {})
                href = p.get("href", f"https://www.instagram.com/p/{c}/")
                issues_str = ", ".join(classify_post(c, p)["issues"]) or "—"
                lines.append(f"- [{c}]({href}) — {issues_str}\n")
            if len(codes) > 20:
                lines.append(f"- ... y {len(codes)-20} más\n")
            lines.append("\n")

    REPORT_PATH.write_text("".join(lines), encoding="utf-8")

    print(f"\n✅ Reporte guardado en: {REPORT_PATH}")
    print(f"✅ Lista re-scraping:   {RESCRAPE_PATH}  ({len(rescrape)} posts)")
    print(f"✅ Lista re-likers:     {RELIKERS_PATH}  ({len(relikers)} posts)")
    print("\nSiguiente paso:")
    print("  python3 scripts/scrape_ig_v2.py --mode rescrape   # re-scraping completo")
    print("  python3 scripts/scrape_ig_v2.py --mode relikers   # solo re-likers")


if __name__ == "__main__":
    main()
