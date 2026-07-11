$ErrorActionPreference = "Stop"
$UninstallPyUrl = "https://raw.githubusercontent.com/Today20092/Davinci-Resolve-TimeTracker/main/uninstall.py"

$uv = (Get-Command uv -ErrorAction SilentlyContinue).Source
if (-not $uv) {
    $uv = @(
        "$env:USERPROFILE\.local\bin\uv.exe",
        "$env:APPDATA\uv\uv.exe",
        "$env:LOCALAPPDATA\Programs\uv\uv.exe"
    ) | Where-Object { Test-Path $_ } | Select-Object -First 1
}
if (-not $uv) {
    throw "uv was not found. Reinstall uv or run uninstall.py with Python 3.10+."
}

$uninstallPy = Join-Path $PSScriptRoot "uninstall.py"
if (-not (Test-Path $uninstallPy)) {
    $uninstallPy = Join-Path ([System.IO.Path]::GetTempPath()) "resolve-time-tracker-uninstall.py"
    Invoke-WebRequest -Uri $UninstallPyUrl -OutFile $uninstallPy
}

& $uv run --python 3.13 --no-project python $uninstallPy @args
if ($LASTEXITCODE -ne 0) {
    throw "The uninstaller exited with code $LASTEXITCODE."
}
