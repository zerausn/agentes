@echo off
title Antigravity — Iniciando Mejorador de Video/Fotos
cd /d "%~dp0"

echo ==========================================================
echo       INICIANDO INTERFAZ GRAFICA DE MEJORAMIENTO
echo ==========================================================
echo.
echo Requisitos: Se abrira una pestana en tu navegador (http://127.0.0.1:7860)
echo.

:: Verificar si el entorno principal existe
if not exist ".venv\Scripts\python.exe" (
    echo [ERROR] No se encontro el entorno virtual en .venv
    pause
    exit /b
)

:: Ejecutar la aplicacion
".venv\Scripts\python.exe" gui_upscaler.py

if %ERRORLEVEL% neq 0 (
    echo.
    echo [ERROR] La aplicacion se detuvo inesperadamente.
    pause
)
