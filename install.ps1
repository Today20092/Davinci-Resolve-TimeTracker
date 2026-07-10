$ErrorActionPreference = "Stop"

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
    Write-Host "Installing uv..."
    powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
    $uv = Find-Uv
}
if (-not $uv) {
    throw "uv install finished, but uv was not found. Restart PowerShell or add uv to PATH, then rerun install.ps1."
}

$env:RESOLVE_TIME_TRACKER_UV = $uv
& $uv run --python 3.13 --no-project python "$PSScriptRoot\install.py" @args
