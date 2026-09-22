# Briefing para IA que trabaja en el repo `agentes` (rama `linux-arm64`)

> **Workspace de trabajo:** `~/Documents/Codex/2026-08-17/rev/work/agentes-linux-arm64/`
> **Repo remoto:** `https://github.com/zerausn/agentes.git`
> **Rama de trabajo:** `linux-arm64` (todo lo de dispositivos móviles: S24, Note9, Vivo, tablet)
> **Rama separada:** `linux` = solo lo del PC Parrot OS. No mezcles.

---

## 1. Documentación que debes leer PRIMERO

Antes de tocar cualquier código, lee estos archivos en este orden:

```
agentes/docs/DECISIONS.md        ← Decisiones arquitectónicas. Por qué está hecho así.
agentes/docs/PROGRESS.md         ← Historial de todo lo implementado. Evita rehacer trabajo.
agentes/meta_uploader/CONTEXT_FOR_AI.md  ← Contexto específico del módulo Meta.
agentes/meta_uploader/AI.md      ← Reglas de trabajo para el módulo Meta.
agentes/docs/FACEBOOK_BIFURCATION.md    ← Arquitectura del sistema bifurcado FB (Teasers/Crudos).
agentes/docs/YOUTUBE_LOTES_NODOS_MOVILES.md ← Arquitectura de descarga YouTube multi-nodo.
agentes/docs/VIGIA_FACEBOOK720_DOZE_FIX.md  ← Por qué el reloj está en bash, no en Python.
```

---

## 2. Arquitectura del sistema (resumen ejecutivo)

### Páginas de Facebook gestionadas
| Página | ID | Propósito |
|--------|----|-----------|
| Performatic Writings Cali | `803559979506784` | Contenido principal (Crudos) |
| Shirabyoshi Writings | `1347014641828725` | Teasers verticales (9:16) |

### Widgets en S24 Ultra (SM-S928B, serial RFCX91HV4GD)
| Widget | Script Bash | Script Python | Función |
|--------|------------|---------------|---------|
| `VIGIA_META720` | `vigia_meta720_termux.sh` | `fb_to_ig_vigia.py` | Crosspost FB → Instagram |
| `4_VIGIA_FB_CRUDOS` | `vigia_facebook720_crudos_termux.sh` | `subir_fb_evacuador_crudos.py` | FB Evacuador videos crudos |
| `4_VIGIA_FB_TEASERS` | `vigia_facebook720_teasers_termux.sh` | `subir_fb_evacuador_teasers.py` | FB Evacuador teasers |
| `3_SUBIR_TEASERS_YT720` | `vigia_teasers_yt720_termux.sh` | `teaser_uploader.py` | Subir teasers a YouTube |

### Regla Anti-Doze (CRÍTICA)
**Nunca uses `time.sleep(720)` en Python.** Android Doze Mode congela Python.
El reloj siempre vive en bash con `termux-wake-lock` + `date +%s` checks cada 15s.
El script Python hace **1 operación y retorna**. Bash decide cuándo volver a llamarlo.
Ver: `docs/VIGIA_FACEBOOK720_DOZE_FIX.md`

### Credenciales y proot
Las variables `META_*` deben tener `export` en `~/.agentes_termux_env` del S24.
**proot-distro limpia el entorno** al hacer `login debian`. Bash debe inyectarlas
explícitamente con `--env VAR=valor` antes del login, O el script Python debe
tener el token como fallback hardcoded en `os.environ.get("VAR", "TOKEN_REAL")`.

---

## 3. Cómo sincronizar con GitHub antes de trabajar

```bash
cd ~/Documents/Codex/2026-08-17/rev/work/agentes-linux-arm64
git pull --rebase --autostash origin linux-arm64
```

**Siempre haz pull antes de editar.** El S24, Note9 y Vivo también pushean a
`linux-arm64`. Si no haces pull primero, tu push será rechazado.

---

## 4. Cómo hacer commit y push

```bash
git add <archivos>
git commit -m "tipo(alcance): descripción corta"
git push origin linux-arm64
```

Si el push es rechazado (otro dispositivo pushó primero):
```bash
git pull --rebase --autostash origin linux-arm64
git push origin linux-arm64
```

### Convención de commits
```
feat(meta): nueva funcionalidad en meta_uploader
fix(meta): corrección de bug en meta
fix(termux): corrección relacionada con proot/Termux
docs: actualización de documentación
sync: <dispositivo> bajó <video_id> (YYYY-MM)
```

---

## 5. Cómo deployar al S24 via ADB

El PC tiene ADB configurado con el S24 conectado por USB (serial `RFCX91HV4GD`).

```bash
# Enviar un archivo Python al S24
cat ruta/al/archivo.py | adb -s RFCX91HV4GD shell run-as com.termux \
  tee /data/data/com.termux/files/usr/var/lib/proot-distro/containers/debian/rootfs/root/agentes/ruta/al/archivo.py > /dev/null

# Ver un log del S24
adb -s RFCX91HV4GD shell run-as com.termux cat /sdcard/Antigravity/widget_logs/NOMBRE_DEL_LOG.log | tail -n 60
```

Los logs de los widgets viven en `/sdcard/Antigravity/widget_logs/` en el S24.

---

## 6. Reglas de documentación (OBLIGATORIO)

### Cuándo documentar
- **Cada vez que implementes algo nuevo:** agrega una sección en `docs/PROGRESS.md`.
- **Cada vez que tomes una decisión de diseño no obvia:** agrega en `docs/DECISIONS.md`.
- **Cada vez que encuentres un bug y lo corrijas:** documenta el problema, la causa raíz y la solución en `docs/DECISIONS.md`.

### Formato para `PROGRESS.md`
```markdown
## Nombre del Feature/Fix (YYYY-MM-DD)
- **Problema:** qué fallaba o qué faltaba.
- **Solución:** qué se implementó.
- **Archivos:** qué se creó o modificó.
- **Verificación:** cómo se confirmó que funciona (log real, prueba, etc.).
```

### Formato para `DECISIONS.md`
```markdown
## YYYY-MM-DD: Título de la decisión

### Contexto
Por qué surgió esta decisión. Qué problema había.

### Decisiones
1. Opción A elegida vs B descartada.
2. ...

### Archivos Modificados
- `ruta/al/archivo.py` — descripción del cambio

### Consecuencia
Qué implicaciones tiene hacia adelante.
```

### Después de cada sesión
1. Actualiza `PROGRESS.md` con todo lo implementado.
2. Actualiza `DECISIONS.md` con cada decisión no trivial.
3. Haz commit con mensaje `docs: <resumen de la sesión>`.
4. Push a `origin linux-arm64`.

---

## 7. Gotchas conocidos (lee esto antes de depurar)

| Síntoma | Causa probable | Solución |
|---------|---------------|----------|
| `TypeError: func() got unexpected kwarg 'page_id'` | La función de `meta_uploader.py` no tiene ese parámetro | Agregar `page_id=None, page_token=None` con `try/finally` |
| El Vigía espera 12h en vez de 12min | `time.sleep()` en Python congelado por Doze | Mover el reloj a bash, Python solo hace 1 operación y retorna |
| Variable `META_*` llega vacía en Python | proot limpia el entorno | Usar fallback hardcoded en `os.environ.get("VAR", "VALOR_REAL")` y `export` en `~/.agentes_termux_env` |
| `git push` rechazado con `fetch first` | Otro nodo pushó antes | `git pull --rebase --autostash origin linux-arm64` antes del push |
| `.git/objects` error de permisos | Algún comando corrió con `sudo` antes | `sudo chown -R $USER:$USER .git` |
| Post de texto gasta el ciclo de 720s | Vigía seleccionó post sin media | El pre-filtro en `_find_newest_uncrossposted()` ya lo resuelve en v4.0 |
| Error `#200 no permission to post videos` | Token incorrecto (SYSTEM_USER en vez de PAGE) | Regenerar Page Access Token vía `GET /{page-id}?fields=access_token` con el System User Token |

---

## 8. Flujo del Vigía FB→IG (fb_to_ig_vigia.py v4.0)

```
Ciclo cada 720s (bash):
├─ Por cada página (Performatic, Shirabyoshi):
│   ├─ Bloque 1: descarga 100 posts → ¿hay uno nuevo con media? → SÍ: candidato
│   │                                                            → NO: Bloque 2
│   │   ... hasta Bloque 5
│   └─ Si no hay candidato en 5 bloques → pasa a fallback
│
└─ Fallback: missing_crossposts_report.json
    └─ Toma el más reciente no publicado → fetch del post vía API → sube
```

**1 post por ciclo.** Python retorna 1 si publicó, 0 si nada nuevo.
El bash espera 720s y vuelve a llamar.

---

## 9. Archivos de referencia rápida

```
agentes/
├── meta_uploader/
│   ├── meta_uploader.py          ← Motor central de API de Meta (FB + IG)
│   ├── fb_to_ig_vigia.py         ← Vigía v4.0: crosspost FB → IG por bloques
│   ├── subir_fb_evacuador_720.py ← Evacuador FB genérico (1 video/ciclo)
│   ├── subir_fb_evacuador_crudos.py   ← Evacuador Performatic Writings
│   ├── subir_fb_evacuador_teasers.py  ← Evacuador Shirabyoshi (teasers)
│   ├── evacuador_historico.py    ← Drena backlog histórico (30 min/ciclo)
│   ├── audit_crosspost.py        ← Genera missing_crossposts_report.json
│   └── missing_crossposts_report.json ← ~8,945 posts de FB no cruzados a IG
├── scripts/linux/
│   ├── vigia_meta720_termux.sh          ← Bash wrapper para fb_to_ig_vigia.py
│   ├── vigia_facebook720_crudos_termux.sh
│   ├── vigia_facebook720_teasers_termux.sh
│   ├── vigia_historico_termux.sh        ← Bash wrapper para evacuador_historico.py
│   └── vigia_teasers_yt720_termux.sh
└── docs/
    ├── DECISIONS.md              ← LEE ESTO PRIMERO
    ├── PROGRESS.md               ← LEE ESTO SEGUNDO
    ├── FACEBOOK_BIFURCATION.md   ← Arquitectura del sistema bifurcado
    └── VIGIA_FACEBOOK720_DOZE_FIX.md ← Por qué el reloj está en bash
```
