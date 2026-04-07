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
