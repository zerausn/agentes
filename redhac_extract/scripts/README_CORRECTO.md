# Método correcto - Descarga de Carruseles y Reels vía CDP sin 403

## Carruseles y Posts (/p/)
1. Navegar al post abriendo la URL completa en el navegador, e.g. `https://www.instagram.com/ccinec__/p/DcXM2P2p4Mf/`
2. **Instagram en modo "full page" (no modal) renderiza todos los slides del carrusel en un grid vertical (1 imagen hero + 3 columnas debajo)**.
3. No se requiere simular clicks en botones "Next" ni modificar la URL con `?img_index=N` (lo cual falla porque IG es un SPA).
4. El método correcto es buscar todas las imágenes del DOM que tengan el tamaño original: `document.querySelectorAll('img')` y filtrar por `naturalWidth >= 500`. 
5. Descargar cada `src` usando Python `requests` directamente. Las imágenes en este grid principal no están ofuscadas en blobs.

## Videos / Reels (/reel/)
1. Los videos se renderizan usualmente como un `blob:https://` inalcanzable directamente.
2. Usar Network Interception de chunks HLS (archivos CDN `/m86/`) genera descargas fallidas de fragmentos incompletos de 1 KB.
3. **Método correcto**: Instagram incluye el JSON completo de inicialización de video dentro de las etiquetas `<script type="application/json">` o scripts de hydration no src.
4. Buscar mediante JS `/"video_versions":\\[(.*?)\\]/` en todos los scripts de la página.
5. Parsear el arreglo JSON capturado, ordenar por mayor resolución (`width`) y descargar la URL `.mp4` directa usando `requests`. 

## Evitar scontent directo
- Nunca hacer peticiones fetch ciegas a URLs `scontent` caducadas. El servidor de Meta valida el hash (e.g. `_nc_ohc`) y si está inválido o no corresponde a tu IP devuelve error 403 Bad URL hash o versiones recortadas.
- Todo scrape de URL debe obtenerse en tiempo real de la página usando CDP.
