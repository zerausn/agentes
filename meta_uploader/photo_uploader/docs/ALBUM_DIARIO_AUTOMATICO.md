# Álbum Diario Automático en Facebook

## Estado operativo

El flujo quedó automatizado con dos fases:

1. `facebook_album_web_auto.py` verifica fechas locales, lista álbumes remotos y crea por navegador los álbumes faltantes.
2. `album_diario.py` sube las fotos por Graph API, publica teaser inmediato y archiva localmente solo cuando Facebook confirma.

Existen tres lanzadores versionados en el repositorio y sus equivalentes en el escritorio (`/home/zerausn/Desktop/subir fotos/`):

1. **`subir_album_diario.sh`**:
   - **Flujo completo:** Ejecuta el preflight de creación de álbumes en Edge (reiniciando el navegador con depuración remota habilitada en el puerto `9222` si es necesario) y luego sube las fotos por la API Graph.
2. **`subir_album_diario_sin_reiniciar.sh`**:
   - **Flujo optimizado:** Realiza una comprobación rápida (`--dry-run`) para contar álbumes faltantes. Si todos existen, omite Edge por completo y sube las fotos directamente. Si faltan, abre Edge (sin reiniciar forzosamente si ya está depurando) para crearlos.
3. **`crear_albumes_facebook_edge_auto.sh`**:
   - **Solo creación:** Lanza únicamente la fase web preflight en Edge para crear los álbumes faltantes en Facebook, sin ejecutar la subida posterior de fotos.

## Fuente única de fotos

Solo se usa esta ruta:

```text
/media/zerausn/D69493CF9493B08B/Users/ZN-/Documents/ADM/Carpeta 1/Fotos
```

Las fechas salen del prefijo del archivo:

```text
YYYYMMDD...
```

Ejemplo:

```text
20251024_183300.jpg -> Fotos 2025-10-24
```

## Reglas de álbum

- Fechas con `2+` fotos: álbum por fecha, con nombre `Fotos YYYY-MM-DD`.
- Fechas con `1` foto: álbum común `Fotos sueltas`.
- Los álbumes individuales de una sola foto que ya fueron creados por web no se borran; quedan como reserva para uso futuro.

## Creación automática de álbumes

La creación directa por API quedó bloqueada por Meta:

```text
(#3) Application does not have the capability to make this API call.
```

Por eso el preflight crea álbumes faltantes por Microsoft Edge usando Chrome DevTools Protocol:

1. Abre `https://www.facebook.com/media/set/create/`.
2. Llena el nombre del álbum.
3. Adjunta una semilla web reducida desde una foto real.
4. Pulsa `Publicar`.
5. Espera confirmación por Graph API con `count >= 1`.

Archivos de control generados en el escritorio:

```text
albumes_por_fecha_detectados.txt
albumes_faltantes_facebook.txt
albumes_creados_web_progress.json
albumes_seed_web.json
```

## Calidad de subida

Para evitar `Invalid parameter` con panorámicas gigantes y mantener calidad visible:

- Lado más largo: `2048px`.
- Remuestreo: `LANCZOS`.
- Color: conversión a `sRGB` cuando hay perfil ICC.
- EXIF: orientación aplicada físicamente y metadata conflictiva eliminada.
- JPEG: `quality=88`, progresivo y optimizado.

Esto evita subir originales de `16320x7532` directo a Graph API, que pueden fallar por dimensiones, memoria descomprimida, aspecto extremo o metadata/EXIF.

## Teaser

- Se publica inmediatamente al terminar de subir el álbum; no se agenda a las `20:00`.
- Si hay `5+` fotos: carrusel de 5 fotos.
- Si hay `2-4` fotos: carrusel con las disponibles.
- Si hay `1` foto: foto-teaser directa.
- Las fotos del teaser se escogen distribuidas por segmentos del álbum, priorizando peso como proxy de nitidez.

## Confirmación y archivado

Antes de mover originales, el script confirma:

1. Álbum accesible por Graph.
2. IDs de fotos accesibles y asociados al álbum.
3. Teaser publicado; si `/{post_id}` tarda, confirma también vía `/{page_id}/published_posts`.

Solo después:

```text
fotos_subidas_album/<nombre_album>/
```

Además mantiene copia/plano legacy en:

```text
fotos_subidas_album/
```

## Recuperación sin duplicados

Si se corta la subida:

```bash
meta_uploader/photo_uploader/subir_album_diario.sh
```

El script reanuda así:

- Lee fotos existentes del álbum remoto.
- Extrae el stem desde el caption `Archive frame: ...`.
- Salta fotos ya subidas.
- Detecta teaser existente por el link del álbum en `published_posts`.
- Solo archiva cuando todo queda confirmado.

## Dependencias

- Microsoft Edge Flatpak instalado y logueado en Facebook.
- `python3` del sistema con `requests`, `websocket-client` y `Pillow`.
- `dcraw` e ImageMagick `convert` para DNG.
- `.env` en `meta_uploader/.env` con:

```text
META_FB_PAGE_ID
META_FB_PAGE_TOKEN
```

No subir `.env`, tokens, logs ni historiales locales generados.
