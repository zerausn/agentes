# Monitor de subida en tiempo real

Herramienta de consola para seguir, en paralelo, los logs de `meta_uploader` y
`youtube_uploader` sin tocar la logica principal de subida.

## Que muestra

- estado actual de Meta Facebook
- estado actual de Meta Instagram
- estado actual de YouTube
- porcentaje del archivo en curso
- bytes confirmados y bytes totales cuando el log los expone
- cantidad de videos subidos hoy por herramienta
- tiempo transcurrido desde la ultima subida exitosa

## Como ejecutarlo

Desde PowerShell en el repo:

```powershell
.\scripts\monitor_realtime.bat
```

O directamente:

```powershell
/media/zerausn/D69493CF9493B08B/Users/ZN-/Documents\Antigravity\.venv\Scripts\python.exe .\scripts\monitor_realtime.py
```

Para una sola captura:

```powershell
.\scripts\monitor_realtime.bat --once
```

## Notas para futuras IAs

Si cambian los formatos de `meta_uploader.log`, `meta_uploader_facebook.log`,
`meta_uploader_instagram.log` o `uploader.log`, este monitor tambien debe
ajustarse. No lo dejen desfasado respecto a los cambios de los runners.

En Windows, evita volver a `cls` en cada ciclo. El monitor ya usa secuencias VT
para redibujar en sitio y asi reducir el parpadeo de la terminal.

Tambien recorta por ancho y usa pantalla alterna para que los mensajes largos no
hagan flooding ni ensucien el buffer de la consola.
