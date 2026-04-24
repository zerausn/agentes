@echo off
title YOUTUBE TEASER UPLOADER (RECICLAJE IG -^> YT)
cd /d "%~dp0"
call ..\..\.venv\Scripts\activate
python teaser_uploader.py
pause
