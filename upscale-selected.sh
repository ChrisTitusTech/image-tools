#!/usr/bin/env bash

set -euo pipefail

APP_NAME="image-upscale"

usage() {
    cat <<'EOF'
Usage: upscale-selected.sh <image1> [image2] ...

Upscales each image argument by calling the globally installed `upscale` command.
EOF
}

if [[ $# -eq 0 ]]; then
    usage >&2
    exit 1
fi

if ! command -v upscale >/dev/null 2>&1; then
    notify-send -u critical "$APP_NAME" "upscale command not found. Run install.sh first." 2>/dev/null || true
    echo "ERROR: 'upscale' command not found in PATH." >&2
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

    echo "Upscaling: $src"
    if upscale "$src"; then
        (( success++ )) || true
    else
        (( failed++ )) || true
    fi
done

summary="${success} file(s) upscaled."
if [[ $failed -gt 0 ]]; then
    summary+=" ${failed} failed."
fi

notify-send "$APP_NAME" "$summary" 2>/dev/null || true

echo "$summary"
