# Photo Uploader — Módulo de Subida de Fotos a Facebook (como Reels)

## ¿Por qué Reels y no fotos normales?

En 2025, el algoritmo de Facebook da **2–3x más alcance orgánico** a los Reels vs publicaciones de foto. Este módulo convierte automáticamente cada foto en un Reel de 5 segundos antes de subirla, maximizando la distribución del contenido.

| Tipo de contenido | Alcance orgánico promedio |
|---|---|
| Foto normal | 4–6% de seguidores |
| Reel | 12–18% (+ no seguidores) |

---

## Estructura del módulo

```
photo_uploader/
├── photo_uploader.py        ← Agente principal (ciclos de subida)
├── album_diario.py          ← Crea álbumes de Facebook por fecha + teaser inmediato
├── photo_to_reel.py         ← Convierte foto JPG/PNG → MP4 5s con FFmpeg
├── fotos_subidas.json       ← Historial (evita re-subidas)
├── photo_uploader.log       ← Log de actividad
├── INICIAR_FOTO_UPLOADER.bat← Lanzador dentro del módulo
└── docs/README.md           ← Esta documentación
```

---

## Carpetas de trabajo

| Rol | Ruta |
|---|---|
| **Fotos pendientes (entrada)** | `/media/zerausn/D69493CF9493B08B/Users/ZN-/Documents/ADM/Carpeta 1\Fotos` |
| **Fotos ya subidas (salida)** | `/media/zerausn/D69493CF9493B08B/Users/ZN-/Documents/ADM/Carpeta 1\fotos_subidas_fb` |

---

## Cómo usarlo

1. Coloca las fotos en la carpeta de entrada.
2. Haz doble clic en **`EJECUTAR_SUBIDAFacebook_Fotos.bat`** en tu escritorio.
3. El agente comenzará a procesar en ciclos de **10 fotos cada 15 minutos**.
4. Las fotos procesadas se moverán automáticamente a `fotos_subidas_fb/`.

---

## Álbum Diario de Facebook

`album_diario.py` es un flujo separado para publicar fotos como álbumes nativos
de Facebook, no como Reels.

### Lógica

1. Agrupa las fotos por fecha detectada en el nombre del archivo (`YYYYMMDD`).
2. Crea o reutiliza un álbum llamado `Fotos YYYY-MM-DD`.
3. Sube todas las fotos de esa fecha al álbum.
4. Muestra progreso del álbum activo: foto actual, porcentaje, faltantes,
   tiempo transcurrido y ETA aproximada.
5. Selecciona hasta 5 fotos para el teaser distribuyendo el álbum por segmentos
   y tomando la foto más pesada de cada segmento como proxy de calidad.
6. Publica un teaser inmediato en inglés con link al álbum y pregunta final.
7. Confirma por Graph API que el álbum, las fotos y el teaser existen y están
   publicados.
8. Solo después de confirmar Facebook, copia/mueve los archivos locales a
   `fotos_subidas_album/Fotos YYYY-MM-DD/`.

### Caption del teaser

```text
New gallery: a night from the performative archive in Cali.

Photos from [date] are now live.
Full album: [album link]
[linktree]

Which photo should become the cover?

#PW #HQ #P
```

### Seguridad operativa

- `META_FB_PAGE_TOKEN` debe ser un Page Access Token (`type=PAGE`).
- Si el token configurado es `USER`, el script intenta derivar un token de
  página en memoria antes de publicar.
- Si Facebook no confirma el álbum completo, el script no mueve las fotos
  locales para evitar marcar como archivado algo no verificado.

---

## Formato de publicación

Cada Reel se publica con la siguiente descripción:
```
[nombre_del_archivo_sin_extension] #PW #HQ #P
```

Ejemplo: si la foto se llama `IMG_20240621_181054.jpg`, el caption será:
```
IMG_20240621_181054 #PW #HQ #P
```

---

## Configuración

El módulo hereda automáticamente las credenciales del `.env` del `meta_uploader` padre:
- `META_FB_PAGE_ID` — ID de tu página de Facebook
- `META_FB_PAGE_TOKEN` — Token de acceso de la página

No necesitas configurar nada extra.

---

## Requisitos

- **FFmpeg** instalado y disponible en el PATH del sistema (para convertir fotos a video).
- El entorno virtual de Antigravity (`.venv`) con `requests` instalado.

---

## Mecanismo anti-duplicados

El archivo `fotos_subidas.json` registra el nombre de cada foto subida exitosamente. Si reincias el agente después de cerrar la ventana, **continuará desde donde se quedó** sin re-subir fotos ya procesadas.
