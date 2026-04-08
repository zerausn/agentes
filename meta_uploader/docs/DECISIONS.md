# Registros de Decisiones - Meta Uploader

## D1: Mantener la version de API configurable
- **Decision:** centralizar la version de Graph API en una variable de entorno
  (`META_GRAPH_API_VERSION`) con default conservador.
- **Razon:** la documentacion oficial ya muestra ejemplos en versiones mas
  nuevas; dejarla configurable reduce deuda tecnica.

## D2: Instagram publica desde contenedor, no desde `media_publish`
- **Decision:** mandar `caption` y metadatos de Reel en la creacion del
  contenedor (`POST /{ig-user-id}/media`) y dejar `media_publish` solo para
  `creation_id`.
- **Razon:** asi lo documenta Meta para el flujo de publicacion.

## D3: Facebook e Instagram requieren polling
- **Decision:** verificar `status_code` en IG y `status` en videos de Facebook
  antes de declarar exito.
- **Razon:** las cargas y publicaciones son asincronas.

## D4: Politica conservadora para el carril compartido
- **Decision:** clasificar como candidato compartido solo lo que cumple el
  subconjunto seguro `3-90s` y vertical.
- **Razon:** Facebook Reels es mas restrictivo que Instagram Reels; esta regla
  evita publicar automaticamente assets que solo uno de los dos soporta bien.

## D5: Artefactos operativos fuera de Git
- **Decision:** ignorar colas generadas, inventarios y videos optimizados.
- **Razon:** contienen rutas locales, ruido operativo y datos derivados.

## D6: Prerrequisitos de App Review versionados en el repo
- **Decision:** versionar una politica de privacidad, instrucciones de
  eliminacion de datos, terminos basicos e icono publico para completar los
  requisitos de App Review de Meta.
- **Razon:** la app no podia avanzar a revision porque faltaban activos basicos
  obligatorios en configuracion.

## D7: Usar GitHub Pages para URLs publicas limpias
- **Decision:** publicar `privacy`, `data deletion` y `terms` como sitio
  estatico gratuito con GitHub Pages en lugar de depender de enlaces
  `github.com/.../blob/...`.
- **Razon:** Meta App Review suele validar mejor URLs publicas simples y
  estables que vistas HTML de GitHub con wrapper de repositorio.

## D8: Mantener `requests` como base y no migrar el uploader al Business SDK
- **Decision:** conservar el cliente HTTP directo con `requests` como base de
  `meta_uploader` y no reescribir el flujo principal sobre
  `facebook-python-business-sdk`.
- **Razon:** al evaluar el repo oficial `facebook/facebook-python-business-sdk`
  se confirmo que el SDK sigue activo y versionado (release `25.0.1` del
  `2026-03-30`), pero su foco visible sigue muy cargado hacia Marketing API,
  objetos autogenerados y ejemplos de anuncios. Para el flujo actual del
  proyecto, que usa publicacion organica, subida resumible y polling fino en
  Pages/Instagram, el codigo directo con `requests` sigue siendo mas claro,
  trazable y facil de depurar. Se consideran rescatables solo patrones puntuales
  del SDK como `debug=True` para imprimir cURL equivalentes, manejo de sesiones
  por token y batch calls para lecturas no criticas.

## D9: Normalizar video de Instagram sobre `REELS` con `share_to_feed`
- **Decision:** usar `media_type=REELS` como carril oficial para publicar video
  en Instagram y exponer `upload_ig_feed_video_resumable(...)` como wrapper con
  `share_to_feed=true`.
- **Razon:** Meta ya devuelve de forma explicita que `media_type=VIDEO` es
  obsoleto para publicar video al feed. Reutilizar el flujo `REELS` evita
  mantener dos implementaciones distintas para Reel y video compartido al feed.

## D10: Dejar Stories fuera del flujo automatizado actual
- **Decision:** no intentar publicar Stories desde la nueva sonda unificada
  mientras la documentacion oficial versionada en el repo no cubra ese flujo.
- **Razon:** es preferible marcar el formato como `skipped` con una razon clara
  antes que inferir endpoints o parametros no respaldados por las fuentes
  oficiales ya auditadas para este subproyecto.

## D11: Vigilar estancamientos de subida cada 10 segundos
- **Decision:** anadir un watchdog de subida que revise progreso cada `10s`,
  alerte tras `2` verificaciones sin avance y ejecute diagnostico basico de
  conectividad contra internet general y `graph.facebook.com`.
- **Razon:** el problema operativo reportado ya no era solo "falla o no falla",
  sino distinguir si el bloqueo venia de wifi/conectividad local o de un stall
  del lado de Meta. El watchdog deja esa senal en logs sin requerir inspeccion
  manual del proceso.
