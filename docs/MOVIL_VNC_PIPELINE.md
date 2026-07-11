# Pipeline Móvil S24 + VNC Note 9 + Tablet

## Dispositivos

| Dispositivo | Modelo | Serial | Usuario Termux | IP |
|---|---|---|---|---|
| S24 Ultra | SM-S928B | RFCX91HV4GD | u0_a447 | 10.31.120.x |
| Note 9 | SM-N9600 | 29396e8c1e3f7ece | u0_a291 | 10.31.120.236 |
| Tablet | SM-X210 | R92Y1073GER | u0_a309 | 10.31.120.11 |

---

## S24: Pipeline Completo (`0_PIPELINE_COMPLETO.sh`)

### Archivos

| Ruta | Función | Script en repo |
|---|---|---|
| `~/.shortcuts/0_PIPELINE_COMPLETO.sh` | Pipeline orquestador | `scripts/linux/pipeline_completo_termux.sh` |
| `~/.shortcuts/0_RENOVAR_REPO.sh` | Renueva el repo (git pull + bootstrap) | `scripts/linux/renovar_repo_termux.sh` |
| `~/.shortcuts/1_CORTAR_TEASERS.sh` | Corta teasers manualmente | `scripts/linux/cortar_teasers_termux.sh` |
| `~/.shortcuts/2_SUBIR_CRUDOS_YT.sh` | Sube crudos manualmente | `scripts/linux/subir_crudos_yt_termux.sh` |
| `~/.shortcuts/3_SUBIR_TEASERS_YT.sh` | Sube teasers manualmente | `scripts/linux/subir_teasers_termux.sh` |
| `~/.shortcuts/4_VIGIA_FACEBOOK.sh` | Evacúa videos a Facebook | `scripts/linux/vigia_facebook_termux.sh` |
| `~/.shortcuts/vigia_meta.sh` | Vigía Meta (FB→IG) | `scripts/linux/vigia_meta_widget.sh` |

### Flujo del pipeline (v6 actual)

```
FASE 1: video_scanner.py → escanea DB
FASE 2: teaser_generator.py → corta teasers de TODOS los crudos (foreground)
FASE 3: Por cada crudo:
  ├─ Lanza teaser_uploader.py --single-file <teaser> &  (UNO POR TEASER, paralelo)
  └─ Espera markers .uploaded de todos sus teasers
FASE 4: Cuando todos los teasers subidos → sleep 2 → uploader.py --video <crudo> &
FASE 5: wait → espera todos los BG
FASE 6: subir_fb_evacuador.py (barrido final)
```

### Sincronización y markers

```
teaser_generator.py escribe:
  .state/<crudo>.done              → todos los teasers cortados
  .state/<teaser>.uploaded         → teaser subido a YouTube (API OK)

Pipeline espera:
  .done + count(.uploaded) == count(teaser.mp4)  → sleep 2 → upload crudo
```

### Modificaciones realizadas

1. **`teaser_generator.py`**:
   - Bitrate HW transcode: `6000k` → `70000k` (calidad 4K sin pérdida)
   - Escritura atómica: genera `<nombre>.part` y renombra a `.mp4` al terminar
   - Markers: `.state/<crudo>.lock` (procesando) y `.state/<crudo>.done` (completo)
   - Salta teasers ya existentes para evitar reprocesos

2. **`teaser_uploader.py`**:
   - Nuevo flag `--single-file <ruta>`: sube un teaser individual
   - Nuevo flag `--state-dir <dir>`: escribe marker `.state/<archivo>.uploaded`
     inmediatamente cuando la API de YouTube confirma la subida (sin esperar
     processing ni mover el archivo)
   - Usado por el pipeline para paralelismo: un proceso por teaser

3. **`subir_fb_evacuador.py`**:
   - Ignora archivos con extensión `.part`
   - Verifica estabilidad: espera 3s sin cambios de tamaño antes de subir
   - Modo paralelo con `threading`: cada video se sube en su propio hilo

### Uso

```bash
# Manual: tocar widget 0_PIPELINE_COMPLETO desde Termux Widget
# O directamente:
bash ~/.shortcuts/0_PIPELINE_COMPLETO.sh
```

---

## Note 9: Servidor VNC + SSH

Nota: no fijar scripts al UID numerico del usuario Termux. En la revision del
2026-07-11 el Note 9 reporto `u0_a291`, aunque instalaciones anteriores
habian usado `u0_a309`. Para ADB, preferir siempre `run-as com.termux`.

### droidVNC-NG

- **Versión:** 2.19.0
- **Puerto VNC:** 5900 (password: `antigravity`)
- **Puerto HTTP (noVNC):** 5800
- **Package:** `net.christianbeier.droidvnc_ng`
- **Accesibilidad:** Permisos otorgados programáticamente vía `input tap`
  desde PC Parrot OS (ADB USB).

### OpenSSH (Termux)

- **Puerto:** 8022
- **Usuario:** verificar con `run-as com.termux id -un` o por `ls -la /data/data/com.termux/files/home`
- **Contraseña:** antigravity
- **Verificar:**
  ```bash
  sshpass -p antigravity ssh -p 8022 <USUARIO_TERMUX>@10.31.120.236
  ```

### ADB (desde PC Parrot)

```bash
# USB
adb -s 29396e8c1e3f7ece shell

# WiFi
adb connect 10.31.120.236:5555
```

---

## Tablet SM-X210: Cliente VNC

### Túnel SSH

La tablet crea un túnel al Note 9 para VNC:

```bash
sshpass -p antigravity ssh -o StrictHostKeyChecking=no \
  -L 5900:localhost:5900 \
  -p 8022 -N u0_a309@10.31.120.236 &
```

### Scripts

| Ruta | Función |
|---|---|
| `~/tunel_vnc.sh` | Solo túnel SSH (mantiene conexión abierta con `while sleep 60`) |
| `~/vnc_control.sh` | Túnel + lanzar freebVNC |
| `~/.shortcuts/6_VNC_NOTE9.sh` | Shortcut Termux Widget (un toque) |

### freebVNC

- **Package:** `com.iiordanov.freebVNC`
- **Conexión guardada:** "Note9" → `localhost:5900`, password `antigravity`
- **noVNC alternativo:** `http://10.31.120.236:5800/vnc.html` en navegador
  (no requiere túnel)

### ADB (desde PC Parrot)

```bash
# WiFi
adb connect 10.31.120.11:41177
```

---

## Diagrama de red

```
PC Parrot OS
  │
  ├── USB ── Note 9 (ADB)
  │              │
  │              ├── droidVNC-NG :5900
  │              ├── noVNC :5800
  │              └── SSH :8022
  │
  └── WiFi ── Tablet SM-X210 :41177 (ADB)
                  │
                  ├── SSH tunnel :5900 → Note9:5900
                  └── freebVNC → localhost:5900
                          │
                          └── Muestra pantalla del Note 9
```
