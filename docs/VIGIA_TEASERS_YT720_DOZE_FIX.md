# VIGIA_TEASERS_YT720 — Fix Android Doze Mode para subida de teasers a YouTube

## Problema

El widget `3_SUBIR_TEASERS_YT` original subía TODOS los teasers pendientes de una sola
vez y terminaba. No había loop, no había wake-lock, no había resiliencia contra Doze.

Para mantener un flujo constante de contenido en YouTube (1 teaser cada 12 minutos),
se necesita un proceso persistente que:
- No sea congelado por Android Doze Mode
- Sepa cuándo YouTube rechaza por límite diario de subidas
- Reintente automáticamente después de 1 hora si se alcanzó el límite

## Solución Implementada

Dos mecanismos clave:

### 1. `teaser_uploader.py --single-file` — sube 1 teaser y retorna
- El flag `--single-file` ya existe en `teaser_uploader.py`
- Usa `--from-orchestrator` para evitar conflicto de lock con otras instancias
- Crea un marker `.uploaded` en `.state/` cuando la subida es exitosa
- El bash loop usa `timeout 180` para no esperar más de 3 minutos por subida

### 2. `vigia_teasers_yt720_termux.sh` — loop bash con reloj del sistema
- Activa `termux-wake-lock` al inicio
- Usa `date +%s` para calcular el epoch objetivo
- Chequea el reloj cada 15 segundos con `sleep 15`
- **Dos modos de operación:**
  - **NORMAL:** espera 720s (12 min) entre subidas
  - **LIMITED:** si YouTube responde `uploadLimitExceeded`, espera 3600s (1h)

```bash
# Núcleo del método:
NEXT_EPOCH=$(( $(date +%s) + 720 ))   # o +3600 en modo LIMITED

while [ $(date +%s) -lt $NEXT_EPOCH ]; do
    sleep 15
done
```

### 3. Detección de límite diario de YouTube
Cuando `teaser_uploader.py` recibe `uploadLimitExceeded`, imprime "LIMIT_EXCEEDED"
en su salida. El bash loop captura esta salida y cambia automáticamente a modo
LIMITED (1h entre reintentos). Cuando una subida en modo LIMITED es exitosa,
vuelve a modo NORMAL (720s).

## Archivos

| Archivo | Ubicación en repo | Destino en dispositivo |
|---------|------------------|----------------------|
| `vigia_teasers_yt720_termux.sh` | `scripts/linux/` | `~/agentes/scripts/linux/` (Termux home) |
| `shortcut_3_SUBIR_TEASERS_YT720.sh` | `scripts/linux/` | `~/.shortcuts/3_SUBIR_TEASERS_YT720.sh` (widget) |
| `3_SUBIR_TEASERS_YT720.sh` | `termux_widgets/` | Referencia (contenido idéntico al shortcut) |
| `teaser_uploader.py` | `youtube_uploader/` | `/root/agentes/youtube_uploader/` (Debian proot) |

## Instalación en un dispositivo nuevo

```bash
# 1. Copiar el bash loop (ya está en ~/agentes si el repo está actualizado)
#    Si no, renovar el repo:
cd ~/agentes && git pull

# 2. Instalar el widget shortcut
cp ~/agentes/scripts/linux/shortcut_3_SUBIR_TEASERS_YT720.sh \
   ~/.shortcuts/3_SUBIR_TEASERS_YT720.sh
chmod +x ~/.shortcuts/3_SUBIR_TEASERS_YT720.sh

# 3. En Android: Settings > Apps > Termux > Batería → "Sin restricciones"
```

## Dependencias

- `termux-api` (para `termux-wake-lock` / `termux-wake-unlock`)
- `proot-distro` con Debian instalado
- `teaser_uploader.py` funcionando con credenciales OAuth
- Teasers generados en `/sdcard/Antigravity/teasers_pendientes/`

## Comportamiento esperado

| Situación | Acción |
|-----------|--------|
| Hay teasers pendientes | Sube 1, espera 720s, repite |
| No hay teasers | Espera 720s, vuelve a revisar |
| YouTube dice "límite diario alcanzado" | Cambia a modo LIMITED (1h entre reintentos) |
| Límite se resetea y subida es exitosa | Vuelve a modo NORMAL (720s) |
| Usuario cierra el widget | `termux-wake-unlock` se ejecuta vía trap |

## Diferencias con VIGIA_FACEBOOK720

| Aspecto | Facebook 720 | Teasers YT 720 |
|---------|-------------|----------------|
| Script Python | `subir_fb_evacuador_720.py` (dedicado) | `teaser_uploader.py --single-file` (existente) |
| Límite diario | No manejado | Detecta `uploadLimitExceeded`, modo LIMITED |
| Timeout | Ninguno | 180s por subida |
| Output dir | `subidos a facebbok` | `videos subidos exitosamente` (via verifier) |

## Dispositivos verificados

| Dispositivo | Estado | Fecha |
|-------------|--------|-------|
| Samsung Note9 | ✅ Implementado | 2026-07-01 |
| Samsung S24 Ultra | 🔄 Pendiente | — |
| Vivo V2058 | 🔄 Pendiente | — |
