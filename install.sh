#!/usr/bin/env sh
set -eu
install_py_url="https://raw.githubusercontent.com/Today20092/Davinci-Resolve-TimeTracker/main/install.py"

echo
echo "Resolve Time Tracker installer"
echo "This will:"
echo "  1. Find uv, or install it if missing."
echo "  2. Download the Python installer if this file was run by itself."
echo "  3. Set up the source checkout, frontend, and DaVinci Resolve menu script."
echo

confirm_continue() {
    if [ ! -t 0 ]; then
        return 0
    fi
    printf 'Do you want to continue? [y/N] '
    read answer
    case "$answer" in
        y|Y|yes|YES) return 0 ;;
        *) echo "Install cancelled."; exit 0 ;;
    esac
}

find_uv() {
    if command -v uv >/dev/null 2>&1; then
        command -v uv
        return 0
    fi
    for candidate in "$HOME/.local/bin/uv" "$HOME/.cargo/bin/uv"; do
        if [ -x "$candidate" ]; then
            printf '%s\n' "$candidate"
            return 0
        fi
    done
    return 1
}

confirm_continue

uv_bin="$(find_uv || true)"
if [ -z "$uv_bin" ]; then
    echo "[bootstrap] uv was not found. Installing uv..."
    if command -v curl >/dev/null 2>&1; then
        curl -LsSf https://astral.sh/uv/install.sh | sh
    elif command -v wget >/dev/null 2>&1; then
        wget -qO- https://astral.sh/uv/install.sh | sh
    else
        echo "Install failed: curl or wget is required to install uv." >&2
        exit 1
    fi
    uv_bin="$(find_uv || true)"
else
    echo "[bootstrap] Found uv: $uv_bin"
fi

if [ -z "$uv_bin" ]; then
    echo "Install failed: uv install finished, but uv was not found. Restart your shell or add uv to PATH, then rerun install.sh." >&2
    exit 1
fi

script_dir="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
install_py="$script_dir/install.py"
if [ ! -f "$install_py" ]; then
    install_py="${TMPDIR:-/tmp}/resolve-time-tracker-install.py"
    echo "[bootstrap] Downloading installer: $install_py_url"
    if command -v curl >/dev/null 2>&1; then
        curl -LsSf "$install_py_url" -o "$install_py"
    elif command -v wget >/dev/null 2>&1; then
        wget -qO "$install_py" "$install_py_url"
    else
        echo "Install failed: curl or wget is required to download the installer." >&2
        exit 1
    fi
fi
echo "[bootstrap] Starting Python installer..."
RESOLVE_TIME_TRACKER_UV="$uv_bin" "$uv_bin" run --python 3.13 --no-project python "$install_py" "$@"
