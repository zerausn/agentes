@echo off
title Antigravity - Subidor de Fotos a Facebook (Reels)
cd /d "C:\Users\ZN-\Documents\Antigravity\agentes\meta_uploader\photo_uploader"

echo ==========================================================
echo   ANTIGRAVITY - SUBIDOR MASIVO DE FOTOS A FACEBOOK
echo ==========================================================
echo.
echo  Modo: Foto -^> Reel de 5 segundos (maximo alcance organico)
echo.
echo  Carpeta de entrada:
echo    C:\Users\ZN-\Documents\ADM\Carpeta 1\Fotos
echo.
echo  Carpeta de fotos ya subidas:
echo    C:\Users\ZN-\Documents\ADM\Carpeta 1\fotos_subidas_fb
echo.
echo  Ritmo : 10 fotos cada 15 minutos
echo  Orden : Las fotos mas pesadas se suben primero
echo.
echo  Presiona cualquier tecla para INICIAR...
echo  (O cierra esta ventana para cancelar)
echo.
pause >nul

echo Iniciando agente...
"C:\Users\ZN-\Documents\Antigravity\.venv\Scripts\python.exe" photo_uploader.py

echo.
echo El agente ha terminado o fue interrumpido.
pause
