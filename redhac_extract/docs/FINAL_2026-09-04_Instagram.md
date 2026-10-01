# REDHAC - Documentación Final Instagram (04/09/2026)

## Estado de Extracción: 100% Completado

Se ha finalizado la extracción total de la cuenta de Instagram `@redhuertosagroecali`. Se obtuvieron y verificaron los **469 posts** públicos disponibles.

### Resultados de la auditoría final
- **Total posts procesados:** 469/469
- **Texto y metadatos capturados:** 469/469 (100%)
- **Likes capturados:** 469/469 (100%)
- **Fechas capturadas:** 428/469 (91.3%)
- **Comentarios capturados:** 90 posts (aquellos que tenían comentarios visibles).
- **Likers (usuarios):** 200 posts (el resto de posts, la API de Instagram bloqueó la solicitud por límites de tasa o configuración de privacidad de la cuenta, sin embargo, el *número total de likes* sí fue capturado para todos).

### Correcciones Técnicas Implementadas (v2)
1. **Solución a `likes=None`**: Instagram oculta el contador visual de likes (en el DOM) para muchos posts, pero el dato real siempre permanece en el `og:description` del código fuente. Se implementó una extracción mixta que prioriza el número real del `og:description`, solucionando el falso reporte de 0 likes. Se corrigieron 420 posts mediante este método.
2. **Estabilidad del WebSocket (CDP)**: 
   - Se aumentó el timeout de 30s a 60s.
   - Se implementó un "ping" de keep-alive para evitar cierres de conexión durante operaciones largas (como el scroll infinito de comentarios).
   - Se limitó el `MAX_ROUNDS` de scroll a 8 (10 segundos) para prevenir bloqueos silenciosos del proceso.
3. **Manejo de Emojis**: La extracción de comentarios y textos ahora preserva todos los emojis utilizando `innerHTML` limpio en lugar de `innerText`.

### Archivos Generados
Los archivos consolidados se encuentran en las siguientes rutas locales (y no fueron subidos a GitHub por políticas de privacidad de datos):

- **Excel Consolidado:** `/media/zerausn/D69493CF9493B08B/Users/ZN-/Documents/UNAD/CURSOS/6/METODOLOGÍA Y GESTIÓN DE LA INVESTIGACIÓN/1/Documentacion/1/REDHAC_FINAL.xlsx` (Hoja `IG_469_Completo`)
- **Documento Markdown de lectura:** `/media/zerausn/D69493CF9493B08B/Users/ZN-/Documents/UNAD/CURSOS/6/METODOLOGÍA Y GESTIÓN DE LA INVESTIGACIÓN/1/Documentacion/1/REDHAC_Instagram.md`
- **JSON Crudo (Backend):** `agentes/redhac_extract/output/ig_full_data.json`

### Scripts Actualizados
Los siguientes scripts han sido probados y pulidos en la rama `linux` de GitHub:
- `scripts/scrape_ig_v2.py`: Scraper principal mejorado.
- `scripts/audit_ig.py`: Herramienta de diagnóstico de integridad de datos.
- `scripts/fill_docs_full.py`: Exportador a Excel y Markdown con soporte para emojis y rutas absolutas.
