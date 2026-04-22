#!/usr/bin/env bash

set -euo pipefail

APP_NAME="image-copy"

usage() {
    cat <<'EOF'
Usage: copy-selected.sh <image1> [image2] ...

Copies each selected image's content to the clipboard via the `copy-image` command.
Works on X11 (requires xclip) and Wayland (requires wl-copy).
EOF
}

if [[ $# -eq 0 ]]; then
    usage >&2
    exit 1
fi

if ! command -v copy-image >/dev/null 2>&1; then
    notify-send -u critical "$APP_NAME" "copy-image command not found. Run install.sh first." 2>/dev/null || true
    echo "ERROR: 'copy-image' command not found in PATH." >&2
    exit 1
fi

for image in "$@"; do
    if copy-image "$image"; then
        notify-send "$APP_NAME" "Copied to clipboard: $(basename "$image")" 2>/dev/null || true
    else
        notify-send -u critical "$APP_NAME" "Failed to copy: $(basename "$image")" 2>/dev/null || true
    fi
done
