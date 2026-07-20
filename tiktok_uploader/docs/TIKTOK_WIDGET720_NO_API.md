# 6_SUBIR_TIKTOK720 — widget sin API oficial

## Objetivo

Publicar en TikTok desde un nodo Android mientras la Content Posting API no este aprobada.
El nodo toma videos ya evacuados a Facebook desde:

```text
/sdcard/Antigravity/subidos a facebbok
```

y, cuando el flujo de TikTok termina correctamente, mueve el archivo a:

```text
/sdcard/Antigravity/subidos a tiktok
```

## Flujo

1. `termux_widgets/6_SUBIR_TIKTOK720.sh` lanza el shortcut.
2. `scripts/linux/vigia_tiktok720_termux.sh` mantiene wake-lock y ejecuta un ciclo cada 720 segundos.
3. `tiktok_uploader/tiktok_evacuador_720.py` selecciona 1 video estable de la cola.
4. El video se comparte a TikTok con `termux-open --send`.
5. La UI se opera con ADB local (`adb -s 127.0.0.1:5555 shell input ...`).
6. Si el ciclo llega a publicar, el archivo se mueve a `subidos a tiktok`.

El script no usa la API oficial de TikTok ni tokens de TikTok Developers.

## Titulos y hashtags

La descripcion reutiliza la logica de YouTube/Facebook, en una sola linea:

- Teaser: `{nombre_limpio} #PW #teaser #{numero} Siguenos tambien en Instagram Facebook Youtube linktr.ee/performaticwritingscali #teatro #performance #escriturasperformaticas`
- No teaser: `{nombre_limpio} #PW Siguenos tambien en Instagram Facebook Youtube linktr.ee/performaticwritingscali #teatro #performance #escriturasperformaticas`

`#teaser` y `#{numero}` solo se agregan cuando el archivo contiene el sufijo `_teaser_N`.
Para Android `input text`, los espacios se envian como `%s`. El archivo `.state/tiktok_caption_actual.txt` conserva la descripcion humana completa.

## Requisitos del nodo Note9

Termux debe tener:

```bash
pkg install android-tools termux-api
```

El mirror usado en el Note9 probado quedo como:

```text
deb https://packages.termux.dev/apt/termux-main stable main
```

ADB local debe estar autorizado:

```bash
adb tcpip 5555
```

Luego, desde Termux:

```bash
adb connect 127.0.0.1:5555
adb devices
```

Debe aparecer:

```text
127.0.0.1:5555    device
```

Si aparece `unauthorized`, aceptar la huella RSA en el telefono y repetir `adb connect`.

## Limitacion importante

`input tap` ejecutado directamente desde Termux/Proot falla con `INJECT_EVENTS`. Por eso el widget usa `android-tools` y ADB local. Si el telefono se reinicia o `adbd` deja de escuchar en TCP, el widget no publica y deja el archivo en cola con error hasta que se reactive `adb tcpip 5555`.

El archivo solo debe moverse a `subidos a tiktok` si despues del tap final la UI sale de TikTok/editor/teclado. Si la descripcion sigue visible, el ciclo se marca como error y el archivo queda en cola.

## Validacion en Note9

Prueba realizada el 2026-07-20:

- Dispositivo: `SM-N9600` (`29396e8c1e3f7ece`)
- Override display: `720x1480`
- Fuente inicial: `/sdcard/Antigravity/subidos a facebbok`
- Resultado: 1 video procesado y movido a `/sdcard/Antigravity/subidos a tiktok`
- Pantalla final: launcher de Samsung, consistente con salida de TikTok despues de publicar
- Caption corregido y validado con `20251018 200806_teaser_2.mp4`: `20251018_200806 #PW #teaser #2 Siguenos tambien en Instagram Facebook Youtube linktr.ee/performaticwritingscali #teatro #performance #escriturasperformaticas`
- Validacion final con guard de salida UI: `20251018 200806_teaser_3.mp4` termino con `foreground=com.sec.android.app.launcher`, `[TIKTOK_OK]` y movimiento confirmado a `subidos a tiktok`.
