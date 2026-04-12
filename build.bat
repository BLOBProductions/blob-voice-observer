@echo off
echo === Building Voice Observer ===
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
    --name VoiceObserver ^
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
    copy config.json dist\VoiceObserver\config.json
) else (
    echo { "mode": "toggle", > dist\VoiceObserver\config.json
    echo "toggle_key": "F6", >> dist\VoiceObserver\config.json
    echo "hold_key": "caps_lock", >> dist\VoiceObserver\config.json
    echo "debounce_ms": 300, >> dist\VoiceObserver\config.json
    echo "vad_aggressiveness": 3, >> dist\VoiceObserver\config.json
    echo "trailing_silence_ms": 120, >> dist\VoiceObserver\config.json
    echo "target_window": "VALORANT", >> dist\VoiceObserver\config.json
    echo "microphone_device_index": "0", >> dist\VoiceObserver\config.json
    echo } >> dist\VoiceObserver\config.json
)

echo.
echo Copying LICENSE, NOTICE, and third-party license texts to dist...
REM Apache 2.0 and MIT both require redistributed binaries to ship the
REM license and attribution alongside. These files must travel with the
REM exe, so we copy everything in third_party\ into the dist folder.
copy LICENSE dist\VoiceObserver\LICENSE
copy NOTICE  dist\VoiceObserver\NOTICE
if not exist dist\VoiceObserver\third_party mkdir dist\VoiceObserver\third_party
xcopy /Y third_party\*.txt dist\VoiceObserver\third_party\

echo.
echo === Build complete ===
echo Output: dist\VoiceObserver\VoiceObserver.exe
echo.
echo To distribute: zip the dist\VoiceObserver folder.
