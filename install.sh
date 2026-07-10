#!/usr/bin/env sh
set -eu

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

uv_bin="$(find_uv || true)"
if [ -z "$uv_bin" ]; then
    echo "Installing uv..."
    if command -v curl >/dev/null 2>&1; then
        curl -LsSf https://astral.sh/uv/install.sh | sh
    elif command -v wget >/dev/null 2>&1; then
        wget -qO- https://astral.sh/uv/install.sh | sh
    else
        echo "Install failed: curl or wget is required to install uv." >&2
        exit 1
    fi
    uv_bin="$(find_uv || true)"
fi

if [ -z "$uv_bin" ]; then
    echo "Install failed: uv install finished, but uv was not found. Restart your shell or add uv to PATH, then rerun install.sh." >&2
    exit 1
fi

script_dir="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
RESOLVE_TIME_TRACKER_UV="$uv_bin" "$uv_bin" run --python 3.13 --no-project python "$script_dir/install.py" "$@"
