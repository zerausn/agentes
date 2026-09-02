# Método correcto - Sin abrir scontent directo

## Correcto (usado para ccinec_DcXM2P2p4Mf.jpg 1440x1800 110K sin cortes)
1. Entrar página por página a https://www.instagram.com/ccinec__/p/DcXM2P2p4Mf/ en pestaña nueva con tu sesión Edge (c_user/xs)
2. Esperar 7s a que cargue el article img
3. Encontrar la foto principal: document.querySelector('article img[src*="scontent"]') con naturalW 1440
4. Hacer Guardar como: abrir nueva pestaña con ese src (og:image) y hacer fetch desde su propio origen (sin CORS) con credentials: include
   ```js
   fetch("https://scontent.cdninstagram.com/v/t51.82787-15/782386362_18031611875838914_893708501948332905_n.webp?stp=c288...")
     .then(r=>r.arrayBuffer())
     .then(buf=>{ const bytes=new Uint8Array(buf); let b=''; for(let i=0;i<bytes.byteLength;i++) b+=String.fromCharCode(bytes[i]); return btoa(b); })
   ```
5. Decodificar base64 y guardar como ccinec_DcXM2P2p4Mf.jpg 1440x1800 WEBP 110K verificado con identify

## Incorrecto (lo que estabas haciendo y da cortes/403)
- Abrir directo https://scontent.cdninstagram.com/v/t51.82787-15/764056633_18025716119896559_8854341444078253792_n.jpg?stp=cmp1_dst-jpg_e35_s640x640_tt6... sin pasar por la página del post -> da 403 Bad URL hash (22 bytes) o imagen recortada 543x543 40K
- Usar Page.captureScreenshot con clip {x,y,w,h} del rect -> 82K recortado 479x599

## Para carruseles
- Detectar button[aria-label="Next"] en el post
- Iterar: src actual -> Guardar como (paso 4) -> click Next -> esperar 4s -> repetir hasta 10 slides
- No abrir scontent con stp=c216 directamente

## Verificación
- identify ccinec_DcXM2P2p4Mf.jpg => WEBP 1440x1800+0+0 (no 543x543)
- file => JPEG progressive 8-bit 1440x1800
- Comparar con screenshot de la página 1920x949 vs downloaded 110K
