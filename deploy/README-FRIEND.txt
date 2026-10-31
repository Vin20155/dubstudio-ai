KhmerDub AI - Portable Windows App
==================================

HOW TO RUN
----------
1. Unzip the whole folder somewhere writable, e.g. D:\KhmerDubAI
   (do NOT run it from inside the ZIP, and avoid C:\Program Files).
2. Double-click KhmerDubAI.exe.
3. A black console window opens and your browser opens http://localhost:8000
   automatically. Keep the console window open while you use the app.
4. Click the "Gemini API Key" button (top right), paste your own free key from
   https://aistudio.google.com/app/apikey , then save.
5. Upload a video, then click "Auto Generate".

UPDATES (ONE CLICK)
-------------------
When a new version is published, open Settings -> Updates, click
"Check for Updates", then "Download & Install".

The app downloads the new version, verifies it, replaces the program files and
restarts automatically. Your projects (data folder), settings and API key
(.env) are kept. Do not close the console window while the update is running.

If the update button says the source is not configured, the app was built
without a release repository; download a fresh ZIP from the person who gave
you the app.

IMPORTANT: KEEP THE FOLDER TOGETHER
-----------------------------------
KhmerDubAI.exe needs these next to it:
  _internal\   (the app itself - do not delete or move)
  bin\         (FFmpeg for video/audio processing)
  .env         (settings; API keys can be entered in the UI instead)
  data\        (created automatically - uploads, results, database)

You only need to share/keep the KhmerDubAI folder. Do not delete _internal.

FIRST RUN / INTERNET
--------------------
Internet is required for:
  - Gemini translation and Gemini speech recognition (your API key)
  - Edge-TTS Khmer voices
  - Downloading the speech/AI models on first use:
      Whisper "small" ~470 MB (the model selected by default)
      Whisper "base"  ~150 MB (if you pick it in the Precision Model list)
      Demucs vocal separator ~350 MB
    They are cached in %USERPROFILE%\.cache\huggingface and reused later.
The first transcription may therefore take a few minutes. Later runs are fast.

NOTES
-----
- If port 8000 is busy, the app automatically uses 8001, 8002, ...
- If the app is already running, launching it again just opens the browser.
- Results are saved under data\processed\ .
- Windows SmartScreen may warn because the exe is unsigned:
  click "More info" -> "Run anyway".
- Troubleshooting: run KhmerDubAI.exe from a Command Prompt and read
  startup.log in the same folder.
- If Windows shows a missing DLL / "VCRUNTIME140.dll" error, install the
  Microsoft Visual C++ 2015-2022 Redistributable (x64) from
  https://aka.ms/vs/17/release/vc_redist.x64.exe and start the app again.
- If the console closes instantly, double-click "KhmerDubAI.exe" from a
  Command Prompt window instead; the error message will stay visible and
  also be written to startup.log.

API KEYS
--------
The included .env is blank on purpose. Enter your Gemini key in the web UI.
Optional OpenAI / CodeCraft keys can be added in the AI Settings dialog.
