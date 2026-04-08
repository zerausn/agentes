# Arquitectura - Meta Uploader

## Proposito

Subir contenido de video a Facebook e Instagram usando Graph API y Video API,
con una capa de automatizacion separada del repo contenedor.

## Componentes

- `meta_uploader.py`: cliente principal de autenticacion, limites, subida y
  polling, ahora con watchdog de estancamiento, diagnostico basico de
  conectividad y una primera capa de retries clasificados para requests JSON y
  uploads binarios.
- `classify_meta_videos.py`: clasifica videos locales para el carril compartido
  Reel/Reel con reglas conservadoras.
- `meta_calendar_generator.py`: construye una cola local de publicacion.
- Scripts de diagnostico: `get_meta_ids.py`, `get_page_token.py`,
  `debug_token.py`, `check_page_v2.py`, `diag_sizes.py`.
- Scripts de operacion: `transcode_batch.py`, `test_batch_upload.py`,
  `test_batch_upload_v2.py`, `test_single_scheduled.py`.
  El runner `test_batch_upload.py` ya puede reintentar un asset transitorio y
  pausar el batch para no consumir la cola a ciegas.

## Carriles funcionales

- **Carril compartido Reel/Reel**: usa el subconjunto mas seguro para publicar
  el mismo asset en Facebook Reels e Instagram Reels.
- **Carril Facebook video estandar**: conserva un flujo separado para videos de
  pagina que no dependan del formato Reel.
- **Stories**: fuera del alcance automatizado actual hasta versionar soporte
  oficial especifico para ese flujo.
- **Artefactos locales**: colas JSON, inventarios y videos optimizados se
  generan localmente y quedan fuera de Git.

## Reglas

- La configuracion sensible vive en variables de entorno.
- El subproyecto debe poder moverse dentro del repo sin romper rutas locales.
- El codigo no debe asumir exito inmediato despues de `finish`; Meta procesa
  videos de forma asincrona y requiere polling.
- Las subidas largas deben alertar si se estancan y registrar si el problema
  parece de conectividad local o de la sesion contra Meta.
- Los runners no deben avanzar automaticamente al siguiente asset cuando el
  ultimo fallo parezca transitorio o de red.
