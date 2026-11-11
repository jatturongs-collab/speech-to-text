# Uninstall Speech to Text Dashboard (Windows)
# Run from the project folder:
#   powershell -ExecutionPolicy Bypass -File .\uninstall.ps1
# Every item asks for confirmation first. Default answer is No.
# The project folder itself and your own audio/video files are never deleted.
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

function Confirm($question) {
    $a = Read-Host "$question [y/N]"
    return ($a -match '^(y|yes)$')
}

function Remove-Item-Safe($path, $label) {
    if (-not (Test-Path $path)) { Write-Host "  (not found) $label"; return }
    if (Confirm "Delete $label ($path)?") {
        Remove-Item -LiteralPath $path -Recurse -Force
        Write-Host "  deleted: $label"
    } else {
        Write-Host "  kept: $label"
    }
}

Write-Host ""
Write-Host "=== Uninstall Speech to Text Dashboard ==="
Write-Host "Make sure the dashboard is closed (Ctrl+C in its PowerShell window)."
Write-Host ""

# 1) Virtual environment (all Python packages)
Remove-Item-Safe ".venv" "Python environment .venv (Streamlit, faster-whisper, ...)"

# 2) Whisper model cache (about 3 GB, shared Hugging Face cache)
$hfHome = if ($env:HF_HOME) { $env:HF_HOME } else { Join-Path $env:USERPROFILE ".cache\huggingface" }
$models = @()
$hub = Join-Path $hfHome "hub"
if (Test-Path $hub) { $models = @(Get-ChildItem $hub -Directory -Filter "models--*faster-whisper*") }
if ($models.Count -eq 0) {
    Write-Host "  (not found) Whisper model cache"
} else {
    foreach ($m in $models) { Remove-Item-Safe $m.FullName "Whisper model cache $($m.Name)" }
}

# 3) Saved data of the app
Remove-Item-Safe "token.json"    "Google sign-in token (token.json)"
Remove-Item-Safe "jobs.json"     "Job list (jobs.json)"
Remove-Item-Safe "history.jsonl" "History log (history.jsonl)"
Remove-Item-Safe "transcripts"   "Saved transcripts folder (transcripts)"
Remove-Item-Safe "__pycache__"   "Python cache (__pycache__)"

# 4) client_secret.json (you may want to keep it for the next install)
Remove-Item-Safe "client_secret.json" "Google OAuth file (client_secret.json)"

# 5) ffmpeg (other programs may use it)
if (Get-Command winget -ErrorAction SilentlyContinue) {
    if (Get-Command ffmpeg -ErrorAction SilentlyContinue) {
        if (Confirm "Uninstall ffmpeg with winget? (other programs may use it)") {
            winget uninstall --id Gyan.FFmpeg -e
        } else { Write-Host "  kept: ffmpeg" }
    } else { Write-Host "  (not found) ffmpeg" }
}

Write-Host ""
Write-Host "Done."
Write-Host "To remove the program completely, close PowerShell and delete this project folder:"
Write-Host "  $PSScriptRoot"
Write-Host "If you used the YouTube tab, you can also revoke access at:"
Write-Host "  https://myaccount.google.com/permissions"
