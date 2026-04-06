# Registro de Decisiones Técnicas - YouTube Uploader

Este documento explica el "porqué" de las decisiones clave tomadas en el proyecto.

## 1. Rotación de Credenciales (GCP Pool)
- **Contexto:** YouTube impone un límite de 10,000 unidades de cuota por proyecto por día. Un `search.list` cuesta 100 unidades y un `update` cuesta 50.
- **Decisión:** Implementar un pool de múltiples credenciales para poder procesar cientos de videos al día sin esperar 24 horas.

## 2. Mecanismo de Parada de Emergencia (Archivo STOP)
- **Contexto:** Las IAs y el usuario necesitan una forma de detener el script sin recurrir a señales de proceso (como SIGINT) que pueden fallar en Windows o dejar hilos de red abiertos.
- **Decisión:** Usar un archivo centinela llamado `STOP`. El uploader lo busca antes de cada subida; si existe, el proceso termina limpiamente.

## 3. Programación Masiva (17:45 Col)
- **Contexto:** El canal recibió el error `uploadLimitExceeded` por tener demasiados videos en estado "Borrador" (Draft).
- **Decisión:** Programar un video por día a las 17:45 hora Colombia. Esto mueve los videos a la cola de "Programados", liberando el límite de subidas diarias del canal.

## 4. Arquitectura de Memoria Agnóstica (`AI.md`)
- **Contexto:** El usuario solicitó un sistema que no sea dependiente de un solo modelo (Claude/Gemini/etc).
- **Decisión:** Usar `AI.md` como estándar de instrucciones y la carpeta `docs/` para el estado persistente. Esto evita la amnesia del modelo entre sesiones.
