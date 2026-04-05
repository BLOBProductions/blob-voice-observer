@echo off
echo === Building Blob Voice Observer ===
echo.

if not exist "vosk-model-small-en-us-0.15" (
    echo ERROR: Vosk model not found. Download it first:
    echo   python -c "import urllib.request,zipfile,os; urllib.request.urlretrieve('https://alphacephei.com/vosk/models/vosk-model-small-en-us-0.15.zip','model.zip'); zipfile.ZipFile('model.zip','r').extractall('.'); os.remove('model.zip')"
    exit /b 1
)

REM Remove broken PyInstaller contrib hook for webrtcvad.
REM It calls copy_metadata('webrtcvad') but we use webrtcvad-wheels which
REM registers under a different metadata name. Without this hook, PyInstaller
REM still finds webrtcvad.py and _webrtcvad.pyd through --hidden-import.
for /f "delims=" %%F in ('dir /s /b venv\Lib\site-packages\_pyinstaller_hooks_contrib\stdhooks\hook-webrtcvad.py 2^>nul') do (
    del "%%F"
    echo Removed broken hook: %%F
)

echo Running PyInstaller...
venv\Scripts\pyinstaller ^
    --noconfirm ^
    --onedir ^
    --name BlobVoiceObserver ^
    --add-data "vosk-model-small-en-us-0.15;vosk-model-small-en-us-0.15" ^
    --collect-all vosk ^
    --collect-all pyaudio ^
    --hidden-import webrtcvad ^
    --hidden-import _webrtcvad ^
    --hidden-import keyboard ^
    src\main.py

echo.
echo Copying config.json to dist...
if exist config.json (
    copy config.json dist\BlobVoiceObserver\config.json
) else (
    echo {"mode": "toggle", "toggle_key": "F6", "hold_key": "caps_lock", "debounce_ms": 300, "vad_aggressiveness": 3, "trailing_silence_ms": 120} > dist\BlobVoiceObserver\config.json
)

echo.
echo === Build complete ===
echo Output: dist\BlobVoiceObserver\BlobVoiceObserver.exe
echo.
echo To distribute: zip the dist\BlobVoiceObserver folder.
