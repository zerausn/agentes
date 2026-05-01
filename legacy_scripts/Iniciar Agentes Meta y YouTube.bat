@echo off
title Agentes de Subida Automatizada (Meta  y  YouTube)
color 0B

echo ========================================================
echo   INICIANDO LOS AGENTES DIARIOS DE META Y YOUTUBE
echo ========================================================
echo.
echo Cerrando instancias anteriores para evitar duplicados...
powershell -Command "Get-Process powershell -ErrorAction SilentlyContinue | Where-Object { $_.CommandLine -match 'START_AGENT' } | Stop-Process -Force"
timeout /t 2 /nobreak >nul

echo.
echo Iniciando Agente Meta...
start "Agente Meta" powershell -NoExit -ExecutionPolicy Bypass -File "C:\Users\ZN-\Documents\Antigravity\agentes\START_AGENT_META.ps1"

echo Iniciando Agente YouTube...
start "Agente YouTube" powershell -NoExit -ExecutionPolicy Bypass -File "C:\Users\ZN-\Documents\Antigravity\agentes\START_AGENT_youtube.ps1"

echo.
echo ========================================================
echo  EXITO: Los agentes ya estan corriendo en nuevas ventanas.
echo  A partir de ahora, cada 24 horas revisarcan tu carpeta:
echo  C:\Users\ZN-\Documents\ADM\Carpeta 1
echo.
echo  Ya puedes cerrar esta ventana negra.
echo ========================================================
pause
