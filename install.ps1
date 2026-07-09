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

$python = Get-Command py -ErrorAction SilentlyContinue
if ($python) {
    & py -3 "$PSScriptRoot\install.py" @args
} else {
    $python = Get-Command python -ErrorAction SilentlyContinue
    if ($python) {
        & python "$PSScriptRoot\install.py" @args
    } else {
        & $uv run --no-sync python "$PSScriptRoot\install.py" @args
    }
}
