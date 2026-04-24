@echo off
title 👁️ AGENTE VIGIA META 3.0
color 0b
cd /d "C:\Users\ZN-\Documents\Antigravity\agentes\meta_uploader"

echo =========================================================
echo       👁️ AGENTE VIGIA META 3.0: ACTIVADO 👁️
echo =========================================================
echo.
echo [+] Proyecto: Cross-posting FB -> IG (Multi-Placement)
echo [+] Frecuencia: Cada 24 Horas
echo [+] Ubicaciones: Feed + Reels + Stories
echo.
echo [!] NO CIERRES ESTA VENTANA SI QUIERES MANTENER EL VIGIA ACTIVO
echo.
echo =========================================================
echo.

python fb_to_ig_vigia.py

if %ERRORLEVEL% NEQ 0 (
    echo.
    echo [ERROR] El Agente se detuvo con un codigo de error: %ERRORLEVEL%
    pause
)
