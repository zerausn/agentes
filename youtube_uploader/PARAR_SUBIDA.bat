@echo off
echo Deteniendo uploader...
type nul > "%~dp0STOP"
echo.
echo ✅ STOP creado. El uploader se detendrá antes del próximo video.
echo    Para reanudar, ejecuta REANUDAR_SUBIDA.bat
pause
