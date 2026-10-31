# Builds, sanitizes and packages a release, then writes release\update.json.
#
# Usage examples:
#   powershell -ExecutionPolicy Bypass -File .\release.ps1 -Repo "myuser/khmerdub-ai"
#   powershell -ExecutionPolicy Bypass -File .\release.ps1 -Version 1.1.1 `
#       -Repo "myuser/khmerdub-ai" -Notes "Fixed translation retries" -Publish
#
# The app reads the manifest from
#   https://github.com/<owner>/<repo>/releases/latest/download/update.json
# so upload BOTH files (zip + update.json) as release assets every time.
param(
    [string]$Version = "",
    [string]$Repo = "",
    [string]$Notes = "",
    [string]$BaseUrl = "",
    [switch]$SkipBuild,
    [switch]$Publish
)

$ErrorActionPreference = "Stop"
Set-Location (Split-Path -Parent $MyInvocation.MyCommand.Path)

$versionFile = "backend\version.py"
if (-not (Test-Path $versionFile)) { throw "Run this script from the project folder." }

if ($Version) {
    $content = Get-Content -LiteralPath $versionFile -Raw
    $content = [regex]::Replace($content, '(?m)^__version__ = ".*"', "__version__ = `"$Version`"")
    Set-Content -LiteralPath $versionFile -Value $content -Encoding utf8 -NoNewline
    Write-Host "==> Version set to $Version" -ForegroundColor Cyan
}

$current = [regex]::Match((Get-Content -LiteralPath $versionFile -Raw), '__version__ = "([^"]+)"').Groups[1].Value
if (-not $current) { throw "Could not read the version from $versionFile" }
Write-Host "==> Releasing KhmerDub AI v$current" -ForegroundColor Cyan

if (-not $Repo) {
    if ($env:KHMERDUB_UPDATE_SOURCE) {
        $Repo = $env:KHMERDUB_UPDATE_SOURCE
    } elseif (Test-Path ".env") {
        $line = Get-Content -LiteralPath ".env" | Where-Object { $_ -match '^KHMERDUB_UPDATE_SOURCE=' } | Select-Object -First 1
        if ($line) { $Repo = ($line -replace '^KHMERDUB_UPDATE_SOURCE=', '').Trim() }
    }
}
if (-not $Repo -and -not $BaseUrl) {
    Write-Warning "No -Repo / -BaseUrl given. The app will not be able to auto-update until a source is set."
}

# 1. Build the app (unless asked to reuse the existing dist).
if (-not $SkipBuild) {
    & powershell -ExecutionPolicy Bypass -File ".\build_exe.ps1"
    # PyInstaller writes warnings to stderr, so PowerShell reports exit code 1
    # even on success. The script throws on real failures, so reaching here is OK.
}

$dist = Join-Path (Get-Location) "dist\KhmerDubAI"
if (-not (Test-Path (Join-Path $dist "KhmerDubAI.exe"))) {
    throw "Build output not found: $dist\KhmerDubAI.exe"
}

# 2. Sanitize: blank API keys, configure the update source, refresh the readme.
$envTemplate = Get-Content -LiteralPath "deploy\.env.template" -Raw
$envTemplate = [regex]::Replace($envTemplate, '(?m)^KHMERDUB_UPDATE_SOURCE=.*$', "KHMERDUB_UPDATE_SOURCE=$Repo")
Set-Content -LiteralPath (Join-Path $dist ".env") -Value $envTemplate -Encoding utf8 -NoNewline
Copy-Item -LiteralPath "deploy\README-FRIEND.txt" -Destination (Join-Path $dist "README-FRIEND.txt") -Force

# Never ship test data or crash logs.
Remove-Item -LiteralPath (Join-Path $dist "data") -Recurse -Force -ErrorAction SilentlyContinue
Remove-Item -LiteralPath (Join-Path $dist "startup.log") -Force -ErrorAction SilentlyContinue
foreach ($old in Get-ChildItem -LiteralPath (Split-Path $dist -Parent) -Directory -Filter "KhmerDubAI.old-*" -ErrorAction SilentlyContinue) {
    Remove-Item -LiteralPath $old.FullName -Recurse -Force -ErrorAction SilentlyContinue
}

# 3. Zip the whole folder (users unzip and double-click the exe).
$releaseDir = Join-Path (Get-Location) "release"
New-Item -ItemType Directory -Force -Path $releaseDir | Out-Null
$zipPath = Join-Path $releaseDir "KhmerDubAI-Windows-Portable.zip"
Remove-Item -LiteralPath $zipPath -Force -ErrorAction SilentlyContinue

Write-Host "==> Creating $zipPath ..." -ForegroundColor Cyan
& tar -a -c -f $zipPath -C (Join-Path (Get-Location) "dist") KhmerDubAI
if ($LASTEXITCODE -ne 0 -or -not (Test-Path $zipPath)) { throw "ZIP creation failed." }

$zipItem = Get-Item -LiteralPath $zipPath
$hash = (Get-FileHash -LiteralPath $zipPath -Algorithm SHA256).Hash.ToLower()

# 4. Build the manifest the app downloads.
if ($BaseUrl) {
    $downloadUrl = $BaseUrl.TrimEnd("/") + "/KhmerDubAI-Windows-Portable.zip"
} elseif ($Repo) {
    $downloadUrl = "https://github.com/$Repo/releases/latest/download/KhmerDubAI-Windows-Portable.zip"
} else {
    $downloadUrl = ""
}

$manifest = [ordered]@{
    version      = $current
    notes        = $Notes
    published_at = (Get-Date).ToUniversalTime().ToString("yyyy-MM-ddTHH:mm:ssZ")
    url          = $downloadUrl
    size         = $zipItem.Length
    sha256       = $hash
}
$manifestPath = Join-Path $releaseDir "update.json"
$manifest | ConvertTo-Json | Set-Content -LiteralPath $manifestPath -Encoding utf8

Write-Host ""
Write-Host "==> Release package ready" -ForegroundColor Green
Write-Host ("    ZIP      : {0} ({1:N1} MB)" -f $zipPath, ($zipItem.Length / 1MB))
Write-Host ("    Manifest : {0}" -f $manifestPath)
Write-Host ("    Version  : {0}" -f $current)
Write-Host ("    SHA-256  : {0}" -f $hash)
Write-Host ""

# 5. Optionally publish with the GitHub CLI.
if ($Publish) {
    $gh = Get-Command gh -ErrorAction SilentlyContinue
    if (-not $gh) {
        Write-Warning "GitHub CLI (gh) is not installed. Upload the two files manually."
    } elseif (-not $Repo -or "://" -in $Repo) {
        Write-Warning "-Publish needs a GitHub repository in the form owner/repo."
    } else {
        Write-Host "==> Publishing GitHub release v$current ..." -ForegroundColor Cyan
        & gh release create "v$current" $zipPath $manifestPath --repo $Repo --title "KhmerDub AI v$current" --notes $Notes
        if ($LASTEXITCODE -ne 0) { throw "gh release create failed (exit $LASTEXITCODE)." }
        Write-Host "==> Published: https://github.com/$Repo/releases/tag/v$current" -ForegroundColor Green
    }
} else {
    $manual = @"
HOW TO PUBLISH THIS RELEASE (manual)
====================================
1. Open https://github.com/$Repo/releases/new (create the repo once if needed).
2. Tag: v$current      Title: KhmerDub AI v$current
3. Upload BOTH files as release assets (names must stay exactly):
     KhmerDubAI-Windows-Portable.zip
     update.json
4. Write release notes (also copied into update.json), then click "Publish release".
5. Tell users: Settings -> Updates -> Check for Updates -> Download & Install.

IMPORTANT: "latest" means the most recently published release. Publish versions
in order, and never re-publish an older version after a newer one.
"@
    Set-Content -LiteralPath (Join-Path $releaseDir "README-UPLOAD.txt") -Value $manual -Encoding utf8
    Write-Host "    Upload instructions: $(Join-Path $releaseDir 'README-UPLOAD.txt')"
}
