@echo off
title KhmerDub AI - Video Dubbing Studio
echo ==================================================================
echo       KhmerDub AI - Video Dubbing Studio
echo       Whisper + SenseVoice + Gemini + Edge-TTS (ភាសាខ្មែរ)
echo ==================================================================

set PYTHON_CMD=C:\Users\ASUS\AppData\Local\Programs\Python\Python310\python.exe
if not exist "%PYTHON_CMD%" (
    set PYTHON_CMD=C:\Users\ASUS\AppData\Local\Programs\Python\Python312\python.exe
)
if not exist "%PYTHON_CMD%" (
    set PYTHON_CMD=python
)

echo Launching with %PYTHON_CMD% ...
"%PYTHON_CMD%" start_app.py
pause
