# Handover - Instrucciones de Entrega

Instrucciones críticas para el inicio de la próxima sesión de trabajo.

## Contexto Inmediato
- El uploader está detenido debido a que se agotó la cuota de las 4 llaves API al intentar programar los borradores acumulados.
- Se logró programar con éxito el primer lote de 36 videos.

## Pasos para la Siguiente IA/Sesión
1.  **Reset de Cuota:** Confirmar que ha pasado el reset diario (02:00 AM Col).
2.  **Finalizar Programación:** Ejecutar `PROGRAMAR_BORRADORES.bat`. Esto debería terminar con los 147 borradores restantes.
3.  **Verificar Límite:** Si la programación termina sin errores de `uploadLimitExceeded`, proceder a `EJECUTAR_SUBIDA.bat` para los videos nuevos de la computadora.

## Cambios recientes y backup
- Se modificó `teaser_generator.py` y `video_helpers.py` para introducir detección HDR y una vía "fast path" (remux) para crudos no-HDR. Antes de desplegar se creó un backup en la ruta `/sdcard/Antigravity/backups/teaser_generator.py.bak` y `/sdcard/Antigravity/backups/video_helpers.py.bak` en el dispositivo S24.

Si algo sale mal con YouTube/Facebook (rechazo por formato o metadata HDR), restaurar los archivos originales desde esos backups y reiniciar el servicio de Teasers.

## Nota sobre Credenciales
- Todos los tokens OAuth (`token_0.json` al `token_3.json`) están vigentes y autorizados por el usuario ZN-. No es necesario abrir el navegador a menos que un token expire.
