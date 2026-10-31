# KhmerDub AI - Professional AI Video Dubbing Studio

An end-to-end web application for AI-powered video dubbing into spoken Khmer (`ភាសាខ្មែរ`) featuring:
- **Speech-to-Text (STT)**: User-selectable choice of:
  - **Whisper** (via `faster-whisper`, models: tiny, base, small, medium, large-v3)
  - **SenseVoiceSmall** (FunASR multilingual speech recognition)
  - **Gemini Multimodal Audio** (high accuracy with timestamped segments)
- **Dialogue Translation & Adaptation**: **Google Gemini** (`gemini-2.5-flash`, `gemini-1.5-flash`) with custom prompt engineering designed specifically for natural Khmer spoken dialogue and syllable-pacing matching.
- **Vocal Separation & BGM Isolation (កាត់ Voice ទុកតែ BGM)**:
  - **Demucs Neural AI**: Isolates clean background music (BGM) and ambient sound effects with vocal speech completely removed.
  - **Fast DSP Center-Channel Filter**: Instantaneous vocal suppression in under 1 second using FFmpeg stereo phase cancellation.
  - Pure BGM preview and download track.
- **Text-to-Speech (TTS)**: **Microsoft Edge-TTS** for Khmer dubbing:
  - `km-KH-PisethNeural` (Male - ពិសិដ្ឋ)
  - `km-KH-SreymomNeural` (Female - ស្រីមុំ)
  - Automatic duration alignment & speed compensation (`atempo`) so voice fits scene cuts.
- **Audio/Video Processing**: **FFmpeg** pipeline:
  - Audio extraction from MP4, MKV, MOV, WEBM, MP3, WAV.
  - **BGM Isolation Mode**: Layers Khmer voiceover on top of clean BGM without original dialogue.
  - Audio Ducking (15% original audio + 100% Khmer voiceover) or Clean Voice Replacement.
  - **Burned-in Animated Hardsubs (Khmer TikTok / Reels Style)**: Hardcode styled `.ass` subtitles directly onto video frames with FFmpeg, featuring viral TikTok Pop, Pill Box, Neon Cyan, Karaoke progressive highlighting, and native Khmer Unicode font rendering (`Kantumruy Pro`, `Khmer OS Battambang`, `Moul`, `Siemreap`).
  - Export dubbed MP4 video, dubbed MP3 audio, clean BGM WAV, and Khmer `.srt` / `.vtt` / `.ass` subtitles.
- **Web Interface**: Modern, responsive dark-mode studio UI with synchronized video player, live dual subtitle overlay, interactive dialogue segment editor, per-segment TTS preview, and export center.

---

## Quick Start

### 1. Launch the Application

Simply double-click:
```bat
run.bat
```
Or run via command line:
```bash
python start_app.py
```
The server will start on `http://localhost:8000` and automatically open your default browser.

### Prebuilt Windows EXE

Build the portable app with:

```powershell
powershell -ExecutionPolicy Bypass -File .\build_exe.ps1
```

The result is `dist\KhmerDubAI\KhmerDubAI.exe`. Keep the `_internal` and `bin`
folders next to the exe. The launcher:

- Reuses an already running instance instead of failing when port 8000 is busy.
- Picks the next free port (8001, 8002, ...) if another program holds 8000.
- Stores uploads, temp files, the database, `.env` and `startup.log` in the
  `data`/app folder next to the exe (or `%LOCALAPPDATA%\KhmerDubAI` when that
  folder is read-only).
- Keeps the console window open on a startup error so the message can be read,
  and writes the same details to `startup.log`.

For troubleshooting, run the exe from a terminal (`cmd` then `KhmerDubAI.exe`)
and inspect `startup.log` in the same folder.

### 2. Configure Gemini API Key

Click the **Gemini API Key** button in the top right corner of the web interface and enter your free key from [Google AI Studio](https://aistudio.google.com/app/apikey). It will be saved securely in your browser's local storage.

### 3. Workflow

1. **Upload**: Drag & drop your video (`.mp4`, `.mov`, `.mkv`, etc.) or audio file.
2. **One-Click Dubbing**: Click **"Auto Dub Video"** to run the full pipeline automatically (STT ➔ Translate ➔ Synthesize ➔ Mix).
3. **Step-by-Step Mode**: Or use individual steps to review, edit, or adjust dialogue before generating the final video:
   - **Step 1: Transcribe (STT)**
   - **Step 2: Translate to Khmer**
   - **Step 3: Synthesize Voices (Edge-TTS)**
   - **Step 4: Mix & Dub Video (FFmpeg)**
4. **Export**: Download your Dubbed Video (MP4), Dubbed Audio (MP3), and Khmer Subtitles (SRT/VTT).

---

## Directory Structure

```
d:\ai-dubbing-video\
├── backend\
│   ├── config.py                 # Paths, models, FFmpeg detection, voice catalog
│   ├── stt_engine.py             # Whisper, SenseVoiceSmall, Gemini STT
│   ├── translation_engine.py     # Gemini Khmer dialogue adaptation
│   ├── tts_engine.py             # Edge-TTS Khmer synthesis & speed adjustment
│   ├── audio_video_processor.py  # FFmpeg audio extraction, mixing, SRT/VTT
│   └── main.py                   # FastAPI server, REST & SSE endpoints
├── frontend\
│   ├── index.html                # Studio interface
│   ├── style.css                 # Dark theme, glassmorphism, Khmer typography
│   └── app.js                    # Interactive video sync, SSE, API client
├── tests\
│   └── test_pipeline.py          # Automated pipeline test suite
├── start_app.py                  # Python entry point
├── run.bat                       # 1-click Windows launcher
└── requirements.txt              # Dependencies
```
