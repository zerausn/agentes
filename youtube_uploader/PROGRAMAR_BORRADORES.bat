@echo off
echo Programando borradores de YouTube...
echo.
echo Este proceso tomará los videos en borrador del canal y les asignará
echo fechas de publicacion: uno por dia a las 5:45 PM hora Colombia.
echo.
python "%~dp0schedule_drafts.py"
echo.
echo Proceso finalizado. Revisa schedule_drafts.log para ver el resultado.
pause
