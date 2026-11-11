# Setup for CPU-only Thai speech-to-text (faster-whisper) on Windows 11
$ErrorActionPreference = "Stop"

function Run($cmd) {
    & $cmd[0] $cmd[1..($cmd.Length - 1)]
    if ($LASTEXITCODE -ne 0) { throw "Command failed: $($cmd -join ' ')" }
}

# 1) ffmpeg
if (Get-Command ffmpeg -ErrorAction SilentlyContinue) {
    Write-Host "ffmpeg already installed - skipping."
} else {
    Write-Host "Installing ffmpeg via winget..."
    winget install --id Gyan.FFmpeg -e --accept-source-agreements --accept-package-agreements
}

# 2) venv on Python 3.13 (faster-whisper's 'av' dependency has no wheels for 3.15 yet)
if (-not (Test-Path ".venv\Scripts\python.exe")) {
    Write-Host "Creating .venv with Python 3.13..."
    Run @("py", "-3.13", "-m", "venv", ".venv")
}

# 3) faster-whisper
Write-Host "Installing faster-whisper via pip..."
Run @(".venv\Scripts\python.exe", "-m", "pip", "install", "--upgrade", "pip")
Run @(".venv\Scripts\python.exe", "-m", "pip", "install", "--upgrade", "faster-whisper", "av<17")  # av>=17 breaks faster-whisper 1.2.1 (metadata_errors)

Write-Host ""
Write-Host "Done. Close and reopen PowerShell so ffmpeg is on PATH, then run:"
Write-Host "  .\.venv\Scripts\python.exe hq_transcribe.py <audio-or-video-file>"
