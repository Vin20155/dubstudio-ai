# Builds the portable Windows app: dist\KhmerDubAI\
# Usage:  powershell -ExecutionPolicy Bypass -File .\build_exe.ps1
$ErrorActionPreference = "Stop"
Set-Location (Split-Path -Parent $MyInvocation.MyCommand.Path)

# A running copy holds dist\KhmerDubAI\KhmerDubAI.exe and data\translation.db,
# which makes PyInstaller fail at the final COLLECT step.
$running = @(Get-Process -Name "KhmerDubAI" -ErrorAction SilentlyContinue)
if ($running.Count -gt 0) {
    throw "KhmerDubAI.exe is running (PID $($running.Id -join ', ')). Close it before building."
}

$python = ".\.venv\Scripts\python.exe"
if (-not (Test-Path $python)) { $python = "python" }

Write-Host "==> Building KhmerDubAI.exe ..." -ForegroundColor Cyan
& $python -m PyInstaller --noconfirm --clean KhmerDubAI.spec
if ($LASTEXITCODE -ne 0) { throw "PyInstaller failed with exit code $LASTEXITCODE" }

$dist = Join-Path (Get-Location) "dist\KhmerDubAI"
if (-not (Test-Path $dist)) { throw "Build output not found: $dist" }

# Refresh the Visual C++ runtime DLLs. PyInstaller can bundle an old
# msvcp140.dll (e.g. 14.28 from a dependency) while other runtime DLLs come
# from a newer version. That mismatch crashes C++ libraries with
# 0xc0000005 (access violation) during speech recognition / audio separation.
Write-Host "==> Refreshing VC++ runtime DLLs ..." -ForegroundColor Cyan
$vcRuntimeDlls = @(
    'msvcp140.dll', 'msvcp140_1.dll', 'msvcp140_2.dll',
    'msvcp140_atomic_wait.dll', 'msvcp140_codecvt_ids.dll',
    'vcruntime140.dll', 'vcruntime140_1.dll', 'vcruntime140_threads.dll',
    'concrt140.dll'
)
$internalDir = Join-Path $dist "_internal"
foreach ($dll in $vcRuntimeDlls) {
    $src = Join-Path $env:SystemRoot "System32\$dll"
    if (Test-Path $src) {
        Copy-Item $src (Join-Path $internalDir $dll) -Force
    }
}
Write-Host "    VC++ runtime refreshed from $env:SystemRoot\System32"

Write-Host "==> Copying runtime files (.env, ffmpeg) ..." -ForegroundColor Cyan
New-Item -ItemType Directory -Force -Path (Join-Path $dist "bin") | Out-Null

if (Test-Path ".env") {
    Copy-Item ".env" (Join-Path $dist ".env") -Force
}

$ffmpegCandidates = @(
    (Join-Path (Get-Location) "bin\ffmpeg.exe"),
    "C:\ffmpeg-8.0.1-essentials_build\bin\ffmpeg.exe",
    (Get-Command ffmpeg -ErrorAction SilentlyContinue).Source
) | Where-Object { $_ -and (Test-Path $_) }

$ffprobeCandidates = @(
    (Join-Path (Get-Location) "bin\ffprobe.exe"),
    "C:\ffmpeg-8.0.1-essentials_build\bin\ffprobe.exe",
    (Get-Command ffprobe -ErrorAction SilentlyContinue).Source
) | Where-Object { $_ -and (Test-Path $_) }

if ($ffmpegCandidates) {
    Copy-Item $ffmpegCandidates[0] (Join-Path $dist "bin\ffmpeg.exe") -Force
    Write-Host "    ffmpeg  <- $($ffmpegCandidates[0])"
} else {
    Write-Warning "ffmpeg.exe was not found. Video/audio processing will need ffmpeg on PATH."
}
if ($ffprobeCandidates) {
    Copy-Item $ffprobeCandidates[0] (Join-Path $dist "bin\ffprobe.exe") -Force
    Write-Host "    ffprobe <- $($ffprobeCandidates[0])"
} else {
    Write-Warning "ffprobe.exe was not found. Media probing will need ffprobe on PATH."
}

$readme = @"
KhmerDub AI - portable build
============================

Run: KhmerDubAI.exe  (double-click)

The app starts a local web server and opens http://localhost:8000 in your
browser. If port 8000 is busy it automatically uses the next free port, and
if KhmerDubAI is already running it simply opens the existing window.

Keep this whole folder together: KhmerDubAI.exe needs the "_internal"
folder and the "bin" folder next to it.

Runtime data (uploads, temp files, database, startup.log) is stored in the
"data" folder next to the exe. API keys can be edited in ".env".

If the window closes, read "startup.log" in this folder for the reason.
"@
Set-Content -Path (Join-Path $dist "README-START.txt") -Value $readme -Encoding UTF8

Write-Host "==> Done: $dist" -ForegroundColor Green
