$ErrorActionPreference = "Stop"
$InstallPyUrl = "https://raw.githubusercontent.com/Today20092/Davinci-Resolve-TimeTracker/main/install.py"

Write-Host ""
Write-Host "Resolve Time Tracker installer"
Write-Host "This will:"
Write-Host "  1. Find uv, or install it if missing."
Write-Host "  2. Download the Python installer if this file was run by itself."
Write-Host "  3. Set up the source checkout, frontend, and DaVinci Resolve menu script."
Write-Host ""

function Find-Uv {
    $uv = Get-Command uv -ErrorAction SilentlyContinue
    if ($uv) {
        return $uv.Source
    }

    $candidates = @(
        "$env:USERPROFILE\.local\bin\uv.exe",
        "$env:APPDATA\uv\uv.exe",
        "$env:LOCALAPPDATA\Programs\uv\uv.exe"
    )
    foreach ($candidate in $candidates) {
        if (Test-Path $candidate) {
            return $candidate
        }
    }
    return $null
}

$uv = Find-Uv
if (-not $uv) {
    Write-Host "[bootstrap] uv was not found. Installing uv..."
    powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
    $uv = Find-Uv
} else {
    Write-Host "[bootstrap] Found uv: $uv"
}
if (-not $uv) {
    throw "uv install finished, but uv was not found. Restart PowerShell or add uv to PATH, then rerun install.ps1."
}

$env:RESOLVE_TIME_TRACKER_UV = $uv
$installPy = Join-Path $PSScriptRoot "install.py"
if (-not (Test-Path $installPy)) {
    $installPy = Join-Path ([System.IO.Path]::GetTempPath()) "resolve-time-tracker-install.py"
    Write-Host "[bootstrap] Downloading installer: $InstallPyUrl"
    Invoke-WebRequest -Uri $InstallPyUrl -OutFile $installPy
}
Write-Host "[bootstrap] Starting Python installer..."
& $uv run --python 3.13 --no-project python $installPy @args
