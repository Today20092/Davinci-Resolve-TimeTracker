$ErrorActionPreference = "Stop"
$InstallPyUrl = "https://raw.githubusercontent.com/Today20092/Davinci-Resolve-TimeTracker/main/install.py"

Write-Host ""
Write-Host "Resolve Time Tracker installer"
Write-Host "This will:"
Write-Host "  1. Find uv, or install it if missing."
Write-Host "  2. Download the Python installer if this file was run by itself."
Write-Host "  3. Set up the source checkout, frontend, and DaVinci Resolve menu script."
Write-Host ""

function Confirm-Continue {
    if (-not [Environment]::UserInteractive) {
        return
    }
    $answer = Read-Host "Do you want to continue? [y/N]"
    if ($answer -notmatch '^(y|yes)$') {
        Write-Host "Install cancelled."
        exit 0
    }
}

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

function Wait-ToClose {
    if (-not [Environment]::UserInteractive) {
        return
    }

    do {
        $answer = Read-Host "Would you like to close this window? [y/N]"
        if ($answer -notmatch '^(y|yes)$') {
            Write-Host "The installer window will remain open. Enter y when you are ready to close it."
        }
    } while ($answer -notmatch '^(y|yes)$')
}

Confirm-Continue

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
try {
    & $uv run --python 3.13 --no-project python $installPy @args
    if ($LASTEXITCODE -ne 0) {
        throw "The Python installer exited with code $LASTEXITCODE."
    }
    Write-Host ""
    Write-Host "Installation finished successfully."
    Write-Host "Installer: $installPy"
    Write-Host "Python runner: $uv"
} catch {
    Write-Host ""
    Write-Host "Installation did not finish successfully."
    Write-Host "Error: $($_.Exception.Message)"
    throw
} finally {
    Write-Host ""
    Wait-ToClose
}
