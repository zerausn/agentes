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

## D17: Crear un runner normal unificado para la jornada 1 de videos crudos
- **Decision:** introducir `run_jornada1_normal.py` como carril operativo
  separado de los scripts `test_*`, generando un calendario local por dias en
  `meta_calendar.json` y ejecutando estas rutas: reel-safe -> `FB Reel + IG Reel`;
  no reel-safe -> `FB Post + IG Feed`; `IG Story` solo como intento
  best-effort cuando el reel del dia es vertical y `<=60s`; `Facebook Stories`
  como salto explicito por soporte oficial aun no versionado.
- **Razon:** el usuario ya no esta en fase de prueba aislada, sino en fase de
  subida normal. Mantener la jornada 1 como un runner propio evita seguir
  mezclando scripts de prueba con operacion real, permite ordenar la cola por
  dias/fechas y deja trazabilidad local del estado del batch sin tocar los
  videos originales ni depender de los videos optimizados.

## D18: Mantener la promocion de videos optimizados bajo opt-in explicito
- **Decision:** usar el carril de videos optimizados para derivar clips
  `shared_reel` e `instagram_story` en `second_pass/queues/`, y solo fusionar
  esos derivados dentro de `pendientes_reels.json` cuando el operador lo pida
  de forma explicita con `--sync-main-reels-queue`.
- **Razon:** la jornada 1 y los videos optimizados deben mantenerse
  desacoplados. Este carril existe para "hacer encajar" el material crudo en
  los carriles `FB Reel + IG Reel` e `IG Story`, pero no debe contaminar la
  cola principal de produccion hasta que el operador decida que esos derivados
  ya estan listos.

## D19: Dejar YOLO como laboratorio separado antes de cualquier integracion
- **Decision:** encapsular el reencuadre inteligente inspirado en
  `performatic_engine` dentro de `second_pass/experimental_yolo_reframer.py`,
  sin conectarlo a colas, runners ni uploads.
- **Razon:** el usuario quiere probar primero si el enfoque aporta valor real.
  Mantenerlo como laboratorio reduce riesgo, evita meter dependencias pesadas
  en el flujo estable y permite comparar resultados antes de decidir una
  integracion en videos optimizados.

## D20: Subir el chunk objetivo de Facebook y reutilizar conexiones
- **Decision:** cambiar el carril `Facebook Post/Reel` para usar sesion HTTP
  persistente por hilo (`requests.Session`) y arrancar con un chunk objetivo de
  `8 MB`, reduciendo el chunk solo cuando aparezcan fallos transitorios.
- **Razon:** con chunks fijos de `1 MB` un video de `~2.6 GB` exige alrededor
  de `2,493` requests multipart, lo que vuelve dominante el overhead de TLS,
  handshake y confirmacion secuencial de Meta. El chunk adaptativo conserva un
  piso de seguridad de `1 MB`, pero evita quedar atrapado siempre en el peor
  caso de rendimiento.

## D21: Persistir `meta_calendar.json` de forma atomica y reanudable
- **Decision:** hacer que `run_jornada1_normal.py` escriba `meta_calendar.json`
  mediante reemplazo atomico, marque el lane activo como `in_progress` antes de
  subirlo y rehidrate el calendario existente al relanzar la jornada.
- **Razon:** en la corrida real del `2026-04-08` el proceso desaparecio sin
  dejar un error final claro, cuando el cuarto video iba por `~76.69%`. Sin
  estado `in_progress` ni reanudacion del calendario, cada relanzamiento se
  apoyaba en reconstruir el plan desde cero y dejaba ambiguo si habia que
  repetir o saltar el asset actual.

## D22: Supervisar jornada 1 con un wrapper local que relance salidas inesperadas
- **Decision:** introducir `run_jornada1_supervisor.py` como wrapper operativo
  recomendado para jornada 1. El supervisor relanza `run_jornada1_normal.py`
  cuando el runner termina antes de completar el calendario y no dejo una pausa
  explicita por fallo (`paused_on_failure`).
- **Razon:** el problema observado ya no era solo fallo transitorio de red
  dentro del upload, sino tambien la posibilidad de que el runner completo
  desapareciera sin completar el lote. El supervisor crea una capa simple de
  autorecuperacion sin convertir un fallo funcional genuino en un loop ciego.

## D23: Persistir checkpoints del upload resumible de Facebook
- **Decision:** guardar checkpoints locales por asset/endpoint en
  `.fb_upload_checkpoints/`, incluyendo `video_id`, `upload_session_id` y
  `current_offset`, y reintentarlos en los flujos `upload_fb_video_standard`
  y `upload_fb_reel`.
- **Razon:** aun con supervisor, una caida a mitad de un archivo de `2-3 GB`
  seguia implicando volver a cero. El checkpoint local reduce ese costo cuando
  Meta mantiene viva la sesion resumible y, si esa sesion ya no sirve, el
  cliente limpia el checkpoint y vuelve a crear una sesion nueva.

## D24: Cortar la jornada viva a un solo dia real
- **Decision:** mantener `--days` como horizonte de planificacion, pero hacer
  que `run_jornada1_normal.py` ejecute como maximo un solo dia real por
  corrida (`--max-live-days=1` por defecto) y que `run_jornada1_supervisor.py`
  deje de relanzar cuando el siguiente `fecha` del calendario aun es futuro.
- **Razon:** el lote del `2026-04-08` demostro que el calendario por si solo no
  espacía publicaciones; sin esta barrera el runner seguia avanzando por
  `2026-04-09`, `2026-04-10`, `2026-04-11`, etc. dentro de la misma noche.
  La regla operativa del usuario es publicar `1 por dia`, asi que la ejecucion
  viva debe frenarse en cuanto complete el cupo del dia.

## D25: Consultar Meta antes de reintentar un asset
- **Decision:** agregar una guardia remota previa a cada dupla del runner,
  consultando `/{page}/videos` y `/{ig-user}/media` para detectar si el stem
  del archivo ya existe publicado. Cuando aparece un match, el resultado se
  registra como `already_exists_remote` y no se vuelve a subir ese asset.
- **Razon:** `20260310_183619.mp4` termino duplicado en Facebook con ids
  `1882074735828642` y `2143750206382044` porque hubo publicaciones reales en
  distintos intentos del runner. El calendario local por si solo no basta para
  deduplicar despues de caidas o confirmaciones tardias de Meta.

## D26: Unificar el lenguaje humano de Meta
- **Decision:** cuando el usuario diga "sube videos a Meta", el entrypoint
  humano recomendado debe ser `schedule_jornada1_supervisor.py`, mientras
  `run_jornada1_normal.py` queda como constructor/runner base y
  `meta_uploader.py` como cliente de bajo nivel.
- **Razon:** esta separacion evita confusion entre la capa de orquestacion y la
  capa de transporte, y deja un solo comando mental para el operador.
