@echo off
echo === Building Blob Voice Observer ===
echo.

if not exist "models\faster-whisper-tiny" (
    echo Downloading faster-whisper tiny model...
    venv\Scripts\python -c "from huggingface_hub import snapshot_download; snapshot_download('Systran/faster-whisper-tiny', local_dir='./models/faster-whisper-tiny')"
    if not exist "models\faster-whisper-tiny" (
        echo ERROR: Model download failed.
        exit /b 1
    )
    echo Model downloaded.
    echo.
)

echo Running PyInstaller...
venv\Scripts\pyinstaller ^
    --noconfirm ^
    --onedir ^
    --name BlobVoiceObserver ^
    --add-data "models\faster-whisper-tiny;models\faster-whisper-tiny" ^
    --collect-all faster_whisper ^
    --collect-all ctranslate2 ^
    --collect-all tokenizers ^
    --collect-all webrtcvad ^
    --hidden-import pyaudio ^
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
