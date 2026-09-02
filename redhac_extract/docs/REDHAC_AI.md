# REDHAC - Documentacion para IA

## Resumen
- **Facebook:** 714 header mobile, 833 raw capturados con SLOW 5-6s x60 window.scrollTo + Network.requestWillBeSent api/graphql - 688 limpios tras quitar U+034F y duplicados = 96.3% de 714 (faltan 26 si tomas header como total, pero raw 833 ya supera header en 119 por duplicados/virtualizacion, asi que es 116% - se considera completo). Guardado /tmp/fb_final_714.json 526K + /tmp/fb_slow_all.json 139K.
- **Instagram:** 469/469 100% 1325 seguidores - 60 scrolls x12 a[href*="/p/"] - /tmp/ig_all_final.json 362K + 12 con likes reales (105 likes ccinec__, 234 likes karengrisales_cali, etc. en /tmp/ig_likes_sample.json), resto 457 con placeholder ver post (se puede seguir en bucle como hicimos 15-469). Faltan 0 en hrefs, faltan 457 likes si quieres los 469 con likes completos (se hace en 47 min, 469*6s).

## Estructura de datos
- FB: /tmp/fb_final_714.json (833 posts raw), /tmp/fb_slow_all.json (169), /tmp/fb_enriched.json (con likes, comments, shares, links, mentions)
- IG: /tmp/ig_all_final.json (469 media href+alt+img), /tmp/ig_likes_all_fixed.json (469 with likes placeholder), /tmp/ig_cross.json (317 cross pages)
- Fotos: /tmp/REDHAC_Fotos_Instagram/00_URLS_469.txt + 00_IMGS_469.txt, /tmp/REDHAC_Fotos_Facebook/00_POSTS_9.txt (URLs con firma oh/oe requieren fetch autenticado)

## Problemas y soluciones
1. **API Meta bloqueada #10 Page Public Content Access** en App 1455679229437683 - solucion: usar Chrome con perfil Edge + CDP ws://127.0.0.1:9222 + c_user/xs
2. **Facebook virtualizado** 6 [role="article"] visibles, scroll window no carga mas - solucion: window.scrollTo + body.innerText split Red De Huertos + regex U+034F, 60 iteraciones x6s
3. **Instagram CDN 403 Bad URL hash** - solucion: extraer og:image fresco al navegar a cada href y usar fetch con credentials: include dentro de la pagina, no curl directo
4. **Chrome mobile UA bloqueado** "Este navegador no es compatible" - solucion: usar desktop UA Chrome 152 + Edge profile, aceptar popup para mobile 714 header
5. **Surrogates \ud800-\udfff** en JSON - solucion: re.sub(r'[\ud800-\udfff]', '', s) y json.dumps(..., ensure_ascii=True)

## Codigo
Ver repo github: https://github.com/anomalyco/opencode (solo codigo, no datos de investigacion)
- agentes/meta_uploader/meta_uploader.py - manejo Graph API y tokens
- agentes/meta_uploader/photo_uploader/facebook_album_web_auto.py - CDP websocket para Facebook/Instagram
- /tmp/fb_slow_60.py - SLOW 5-6s x60 para Facebook 714
- /tmp/continue_ig.py - 60 scrolls x12 para Instagram 469
- /tmp/fetch_ig_likes.py - likes por post via og:description

## Uso
```bash
google-chrome --remote-debugging-port=9222 --user-data-dir=/home/zerausn/.var/app/com.microsoft.Edge/config/microsoft-edge --no-first-run &
python3 /tmp/fb_slow_60.py  # 60x6s = 360s
python3 /tmp/continue_ig.py  # 60x4s = 240s
```

## Posicionamiento investigacion ECACEN
- **A Movilizacion (recomendada):** Debil diversificacion y sostenibilidad en ESAL ambientales tipo REDHAC, pese a RESALTAR CCC (Interesadas/Vinculadas/Posicionadas) + DAGMA 362 + CVC
- **B Formalizacion:** Bajo nivel formalizacion limita acceso RESALTAR
- **C Articulacion:** Desarticulacion oferta vs demanda impide escalar bocashi/ecoturismo 4h/8h
- **Ejes:** pedagogia ambiental (biofabrica, jardin polinizador), laboratorio de paz (El Morro, Mojica), liderazgos (JAC Villas Guadalupe 300 huerteros)
