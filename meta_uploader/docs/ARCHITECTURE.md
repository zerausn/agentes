# Arquitectura - Meta Uploader

## Proposito

Subir contenido de video a Facebook e Instagram usando Graph API, con una capa
de automatizacion separada del repo contenedor.

## Componentes previstos

- `meta_uploader.py`: cliente principal para limites, subida y publicacion.
- `.env`: credenciales locales no versionadas.
- `requirements.txt`: dependencias de Python del subproyecto.

## Reglas

- La configuracion sensible vive en variables de entorno.
- El subproyecto debe poder moverse dentro del repo sin romper rutas locales.
- La logica de Meta no debe mezclarse con la de `youtube_uploader`.
