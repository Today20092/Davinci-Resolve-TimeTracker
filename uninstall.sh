#!/usr/bin/env sh
set -eu

uninstall_py_url="https://raw.githubusercontent.com/Today20092/Davinci-Resolve-TimeTracker/main/uninstall.py"
uv_bin="$(command -v uv || true)"
if [ -z "$uv_bin" ]; then
    for candidate in "$HOME/.local/bin/uv" "$HOME/.cargo/bin/uv"; do
        if [ -x "$candidate" ]; then uv_bin="$candidate"; break; fi
    done
fi
if [ -z "$uv_bin" ]; then
    echo "uv was not found. Reinstall uv or run uninstall.py with Python 3.10+." >&2
    exit 1
fi

script_dir="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
uninstall_py="$script_dir/uninstall.py"
if [ ! -f "$uninstall_py" ]; then
    uninstall_py="${TMPDIR:-/tmp}/resolve-time-tracker-uninstall.py"
    if command -v curl >/dev/null 2>&1; then
        curl -LsSf "$uninstall_py_url" -o "$uninstall_py"
    elif command -v wget >/dev/null 2>&1; then
        wget -qO "$uninstall_py" "$uninstall_py_url"
    else
        echo "curl or wget is required to download the uninstaller." >&2
        exit 1
    fi
fi

"$uv_bin" run --python 3.13 --no-project python "$uninstall_py" "$@"
