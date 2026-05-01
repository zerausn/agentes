@echo off
title Procesamiento Masivo Antigravity
cd /d "C:\Users\ZN-\Documents\Antigravity\agentes\video_enhancer_4k"

echo ==========================================================
echo        AUTOMATIZACION: MEJORA DE FOTOS Y VIDEOS
echo ==========================================================
echo.
echo Se van a abrir DOS (2) ventanas separadas:
echo - Una ventana se encargara exclusivamente de las Fotos.
echo - La otra ventana se encargara exclusivamente de los Videos.
echo.
echo ^> Si solo quieres procesar fotos, cierra la ventana negra de los videos.
echo ^> Si solo quieres procesar videos, cierra la ventana negra de las fotos.
echo.
echo Las ventanas se retomaran desde donde quedaron si las interrumpes.
echo.
echo Presiona alguna tecla para ABRIR LAS VENTANAS... O cierra esta para cancelar.
pause >nul

:: Lanzar las dos ventanas de comandos en paralelo ejecutando cada modulo de forma exclusiva
start "MASIVO: FOTOS (Antigravity CPU/IA)" cmd /k "title MASIVO: FOTOS (Antigravity AI/NCNN) & "C:\Users\ZN-\Documents\Antigravity\agentes\video_enhancer_4k\.venv\Scripts\python.exe" auto_batch_upscale.py --fotos"
start "MASIVO: VIDEOS (Antigravity Rapido)" cmd /k "title MASIVO: VIDEOS (Antigravity FFmpeg Rapido) & "C:\Users\ZN-\Documents\Antigravity\agentes\video_enhancer_4k\.venv\Scripts\python.exe" auto_batch_upscale.py --videos"

echo.
echo Las dos interfaces de automatizacion han sido lanzadas!
echo Puedes cerrar este lanzador principal.
pause
