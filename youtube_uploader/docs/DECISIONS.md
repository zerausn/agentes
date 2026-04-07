# Registro de Decisiones Tecnicas - YouTube Uploader

Este documento explica el por que de las decisiones clave tomadas en el
proyecto.

## 2026-04-06: Mover `youtube_uploader` a la raiz del repo contenedor
- **Contexto:** el subproyecto habia quedado anidado por error dentro de
  `agentes/agentes/youtube_uploader`.
- **Decision:** ubicarlo en `youtube_uploader/` y reemplazar rutas absolutas de
  autoubicacion por rutas calculadas desde `__file__`.
- **Motivo:** evitar roturas al reorganizar el repo y alinear la estructura con
  la arquitectura declarada del workspace.

## 2026-04-06: Estrategia de doble via (double track)
- **Decision:** implementar calendarios paralelos para videos y shorts.
- **Motivo:** maximizar alcance y detectar huecos de programacion por tipo.

## 2026-04-06: Clasificacion de shorts (regla de 3 minutos)
- **Decision:** adoptar la politica nueva de YouTube para shorts verticales de
  hasta 3 minutos.
- **Motivo:** alinear la clasificacion local y la del canal con la politica
  vigente.

## 2026-04-06: Prefijo de titulos `PW`
- **Decision:** cambiar el prefijo de "Performatic Writings" a `PW`.
- **Motivo:** ganar brevedad y consistencia visual.

## Rotacion de credenciales (GCP pool)
- **Contexto:** YouTube impone limites diarios por proyecto.
- **Decision:** usar un pool de multiples credenciales para procesar cientos de
  videos al dia sin esperar 24 horas.

## Mecanismo de parada de emergencia (archivo `STOP`)
- **Contexto:** las IAs y el usuario necesitan una forma fiable de parar el
  proceso en Windows.
- **Decision:** usar un archivo centinela `STOP` que el uploader revisa antes
  de cada subida.

## Programacion masiva a las 17:45 Colombia
- **Contexto:** el canal recibio `uploadLimitExceeded` por acumulacion de
  borradores.
- **Decision:** programar un video por dia a las 17:45 hora Colombia para mover
  los videos a la cola de programados.

## Arquitectura de memoria agnostica (`AI.md` + `docs/`)
- **Contexto:** el usuario pidio un sistema no atado a un solo modelo.
- **Decision:** usar `AI.md` como capa de instrucciones y `docs/` como memoria
  durable del subproyecto.
