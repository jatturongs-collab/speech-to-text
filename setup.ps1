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

# 2) Python 3.13, installed side by side with any other version (3.14, 3.15 ... stay untouched).
#    faster-whisper's dependencies ('av<17', 'onnxruntime') have no wheels for 3.15 yet.
function Has-Py313 {
    if (-not (Get-Command py -ErrorAction SilentlyContinue)) { return $false }
    py -3.13 --version 2>$null | Out-Null
    return ($LASTEXITCODE -eq 0)
}
if (-not (Has-Py313)) {
    Write-Host "Installing Python 3.13 via winget (your other Python versions are not changed)..."
    winget install --id Python.Python.3.13 -e --accept-source-agreements --accept-package-agreements
    # pick up the new PATH in this window
    $env:Path = [Environment]::GetEnvironmentVariable("Path", "Machine") + ";" + [Environment]::GetEnvironmentVariable("Path", "User")
    if (-not (Has-Py313)) {
        throw "Python 3.13 was installed but is not visible yet. Close PowerShell, open it again and re-run setup.ps1."
    }
}

# 3) venv on Python 3.13
if (-not (Test-Path ".venv\Scripts\python.exe")) {
    Write-Host "Creating .venv with Python 3.13..."
    Run @("py", "-3.13", "-m", "venv", ".venv")
}

# 4) All Python packages of the dashboard (faster-whisper, Streamlit, YouTube libraries, av<17 ...)
Write-Host "Installing packages from requirements.txt via pip..."
Run @(".venv\Scripts\python.exe", "-m", "pip", "install", "--upgrade", "pip")
Run @(".venv\Scripts\python.exe", "-m", "pip", "install", "-r", "requirements.txt")  # requirements.txt pins av<17 (av>=17 breaks faster-whisper 1.2.1: metadata_errors)

Write-Host ""
Write-Host "Done. Close and reopen PowerShell so ffmpeg is on PATH, then run the dashboard:"
Write-Host "  .\.venv\Scripts\python.exe -m streamlit run app.py"
Write-Host "or the command-line transcriber:"
Write-Host "  .\.venv\Scripts\python.exe hq_transcribe.py <audio-or-video-file>"
