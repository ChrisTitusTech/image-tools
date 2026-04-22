#!/usr/bin/env bash

set -euo pipefail

APP_NAME="image-resize"

usage() {
    cat <<'EOF'
Usage: resize-selected.sh <image1> [image2] ...

Prompts for a WIDTHxHEIGHT target, then resizes each selected image in place by
calling the globally installed `resize` command.
EOF
}

if [[ $# -eq 0 ]]; then
    usage >&2
    exit 1
fi

if ! command -v resize >/dev/null 2>&1; then
    notify-send -u critical "$APP_NAME" "resize command not found. Run install.sh first." 2>/dev/null || true
    echo "ERROR: 'resize' command not found in PATH." >&2
    exit 1
fi

if ! command -v zenity >/dev/null 2>&1; then
    notify-send -u critical "$APP_NAME" "zenity is required for the Thunar prompt." 2>/dev/null || true
    echo "ERROR: 'zenity' command not found in PATH." >&2
    exit 1
fi

dimensions=$(zenity --entry \
    --title="Resize Image" \
    --text="Enter target dimensions in WIDTHxHEIGHT format:" \
    --entry-text="1920x1080") || exit 0

if [[ ! "$dimensions" =~ ^[[:space:]]*[0-9]+[[:space:]]*[xX][[:space:]]*[0-9]+[[:space:]]*$ ]]; then
    notify-send -u critical "$APP_NAME" "Invalid dimensions: ${dimensions}" 2>/dev/null || true
    echo "ERROR: dimensions must be in WIDTHxHEIGHT format." >&2
    exit 1
fi

success=0
failed=0

for src in "$@"; do
    if [[ ! -f "$src" ]]; then
        echo "Skipping (not a file): $src"
        (( failed++ )) || true
        continue
    fi

    echo "Resizing: $src"
    if resize "$src" "$dimensions"; then
        (( success++ )) || true
    else
        (( failed++ )) || true
    fi
done

summary="${success} file(s) resized."
if [[ $failed -gt 0 ]]; then
    summary+=" ${failed} failed."
fi

notify-send "$APP_NAME" "$summary" 2>/dev/null || true
echo "$summary"