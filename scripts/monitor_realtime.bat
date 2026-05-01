@echo off
setlocal

set "ROOT=C:\Users\ZN-\Documents\Antigravity"
set "PYTHON=%ROOT%\.venv\Scripts\python.exe"
set "SCRIPT=%ROOT%\agentes\scripts\monitor_realtime.py"

if exist "%PYTHON%" (
    "%PYTHON%" "%SCRIPT%" %*
) else (
    python "%SCRIPT%" %*
)

endlocal
