@echo off
echo Iniciando subida de videos a YouTube...
echo.
echo Para DETENER: haz doble click en PARAR_SUBIDA.bat
echo.
python "%~dp0uploader.py"
echo.
echo El uploader ha finalizado.
echo Sincronizando playlist de engagement...
python "%~dp0manage_playlist.py"
echo Proceso de sincronización terminado.
pause
