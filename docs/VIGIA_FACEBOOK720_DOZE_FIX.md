# VIGIA_FACEBOOK720 — Fix Android Doze Mode

## Problema

El script `4_VIGIA_FACEBOOK720.sh` que corre en Android (Termux + proot-distro Debian)
usaba `time.sleep(720)` dentro del script Python para esperar 12 minutos entre subidas.

**Android Doze Mode** suspende el proceso cuando la pantalla se apaga, congelando
cualquier `sleep` largo. Resultado confirmado en logs reales:

| Ciclo | Pausa esperada | Pausa real |
|-------|---------------|-----------|
| 1 | 12 min | **62 min** ❌ |
| 2 | 12 min | **62 min** ❌ |
| 3 | 12 min | **90 min** ❌ |

## Solución Implementada

Dos cambios clave:

### 1. `subir_fb_evacuador_720.py` — sube UN video y retorna
- **Antes:** el Python subía todos los videos con `time.sleep(720)` entre cada uno
- **Ahora:** sube solo el primer video disponible y termina (exit 0=ok, 2=vacío, 1=error)
- El loop/espera lo controla el bash (que corre en Termux, no dentro de proot)

### 2. `vigia_facebook720_termux.sh` — loop bash con reloj del sistema
- Activa `termux-wake-lock` al inicio (impide que Doze suspenda)
- Usa `date +%s` para calcular el epoch objetivo: `NOW + 720`
- Chequea el reloj cada 15 segundos con `sleep 15`
- **Si Android pausa el proceso**, cuando despierte `date +%s` devuelve la hora
  real — si ya pasaron 720s, sube inmediatamente sin retraso adicional

```bash
# Núcleo del método:
NEXT_EPOCH=$(( $(date +%s) + 720 ))

while [ $(date +%s) -lt $NEXT_EPOCH ]; do
    sleep 15   # chequeo corto, no un sleep largo
done
# → procede sin importar cuánto durmió Android
```

## Resultado Certificado (test real en Note9)

```
TEST REAL 720s — METODO RELOJ SISTEMA
Inicio: 2026-06-21 20:13:58

[WAKE-LOCK] ACTIVADO
[CICLO 1] Siguiente subida en 720s — a las 20:26:01
[RELOJ] Hora alcanzada: 20:26:04

Tiempo planeado : 720s
Tiempo real     : 723s
Diferencia      : 3s
VEREDICTO: ✅ OK — el reloj no fue bloqueado por Doze.
```

**Solo 3 segundos de diferencia** vs los 50-78 minutos de antes.

## Archivos

| Archivo | Ubicación en repo | Destino en dispositivo |
|---------|------------------|----------------------|
| `subir_fb_evacuador_720.py` | `meta_uploader/` | `/root/agentes/meta_uploader/` (dentro de Debian proot) |
| `vigia_facebook720_termux.sh` | `scripts/linux/` | `~/agentes/scripts/linux/` (Termux home) |
| `shortcut_4_VIGIA_FACEBOOK720.sh` | `scripts/linux/` | `~/.shortcuts/4_VIGIA_FACEBOOK720.sh` (widget Termux) |

## Instalación en un dispositivo nuevo

```bash
# 1. Renovar repo en Termux (ya existente)
cd ~/agentes && git pull

# 2. Copiar el Python al Debian proot
cp ~/agentes/meta_uploader/subir_fb_evacuador_720.py \
   /data/data/com.termux/files/usr/var/lib/proot-distro/installed-rootfs/debian/root/agentes/meta_uploader/

# 3. Hacer ejecutable el shortcut
cp ~/agentes/scripts/linux/shortcut_4_VIGIA_FACEBOOK720.sh \
   ~/.shortcuts/4_VIGIA_FACEBOOK720.sh
chmod +x ~/.shortcuts/4_VIGIA_FACEBOOK720.sh

# 4. En Android: Settings > Apps > Termux > Batería → "Sin restricciones"
```

## Dispositivos verificados

| Dispositivo | Estado | Fecha |
|-------------|--------|-------|
| Samsung Note9 | ✅ Implementado y certificado (723s real vs 720s) | 2026-06-21 |
| Samsung S24 Ultra | 🔄 Pendiente implementación | — |
| Vivo | 🔄 Pendiente implementación | — |

## Configuración recomendada en Android

Para maximizar la fiabilidad, configura en el dispositivo:

1. **Settings → Apps → Termux → Batería → Sin restricciones** (Unrestricted)
2. **Recientes → mantener Termux anclado** (no deslizar para cerrar)
3. El `termux-wake-lock` del script ya maneja el resto automáticamente
