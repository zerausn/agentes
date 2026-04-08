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

## D10: Mantener Facebook Stories fuera del flujo automatizado actual
- **Decision:** no intentar publicar Stories de Facebook Pages desde la sonda
  unificada mientras no exista una guia oficial equivalente claramente
  respaldada en las fuentes versionadas del repo.
- **Razon:** en la revision de documentacion oficial de esta ronda si aparecio
  soporte documentado para `Instagram Stories`, pero no se encontro un carril
  equivalente y confirmado para `Facebook Page Stories` en los endpoints ya
  auditados (`/videos`, `/video_reels`, Page Stories API).

## D11: Vigilar estancamientos de subida cada 10 segundos
- **Decision:** anadir un watchdog de subida que revise progreso cada `10s`,
  alerte tras `2` verificaciones sin avance y ejecute diagnostico basico de
  conectividad contra internet general y `graph.facebook.com`.
- **Razon:** el problema operativo reportado ya no era solo "falla o no falla",
  sino distinguir si el bloqueo venia de wifi/conectividad local o de un stall
  del lado de Meta. El watchdog deja esa senal en logs sin requerir inspeccion
  manual del proceso.

## D12: Habilitar `Instagram Stories` solo con flujo oficial `STORIES`
- **Decision:** exponer `upload_ig_story_video_resumable(...)` sobre el mismo
  carril resumible de Instagram, pero creando contenedor con
  `media_type=STORIES`.
- **Razon:** la documentacion oficial consultada en esta ronda ya incluye
  `Story posts` y `POST /{ig-user-id}/media?media_type=STORIES&upload_type=resumable`.
  Eso permite dejar de marcar `Instagram Stories` como no soportado por
  documentacion, aunque la primera prueba viva aun falle en procesamiento.

## D13: Derivar un clip vertical corto cuando la cola Reel esta vacia
- **Decision:** cuando `pendientes_reels.json` no tenga activos compatibles,
  generar una copia local de prueba en `1080x1920`, `30s`, `H.264/AAC` para
  validar `IG Story`, `IG Reel` y `FB Reel` sin esperar nuevo material fuente.
- **Razon:** la cola real de reels seguia vacia, pero bloquear las pruebas por
  eso impedia verificar si el carril compartido ya estaba funcional con un
  asset que si cumpliera el subconjunto seguro.

## D14: Propagar `upload_session_id` en `Facebook /videos finish`
- **Decision:** incluir `upload_session_id` en el `finish_payload` del flujo
  `upload_fb_video_standard(...)` cuando Meta lo devuelve en `upload_phase=start`.
- **Razon:** la prueba viva de `Facebook Post` ya no fallo por conectividad,
  sino por un error explicito `(#194) Requires all of the params: upload_session_id`.
  El ajuste alinea el cliente con la publicacion documentada de video estandar.

## D15: Introducir retries clasificados en la capa HTTP y binaria
- **Decision:** endurecer `meta_uploader.py` con retries manuales sobre
  `_request_json(...)` y `_post_binary(...)`, clasificando errores como
  `dns_resolution`, `timeout`, `connection_reset`, `local_socket_error` o
  `http_<status>`, y exponer el ultimo estado operativo al runner.
- **Razon:** la corrida normal de `15 minutos` mostro un patron mixto de fallos
  transitorios en `Facebook Post` (`ConnectionResetError(10054)`,
  `NameResolutionError`, `OSError(22)` y stalles detectados por el watchdog).
  Sin clasificacion ni retries, el batch seguia quemando cola aunque la causa
  fuera transitoria o de conectividad local.

## D16: No quemar cola ante fallos transitorios del asset actual
- **Decision:** hacer que `test_batch_upload.py` reintente el mismo asset cuando
  el ultimo estado del uploader sea transitorio, y pausar el batch si se agotan
  esos reintentos.
- **Razon:** avanzar automaticamente al siguiente video despues de un fallo
  transitorio degrada la cola y no ayuda a distinguir entre un video roto y un
  problema momentaneo de red, DNS o socket.
