#!/usr/bin/env bash
# =============================================================================
#  convert-to-webp.sh
#  Converts one or more images to WebP using configurable width/quality.
#  Usage: convert-to-webp.sh <image1> [image2] ...
# =============================================================================

set -euo pipefail

# ---------- configuration ----------------------------------------------------
CONFIG_DIR="${XDG_CONFIG_HOME:-$HOME/.config}/webp-convert"
CONFIG_FILE="${CONFIG_DIR}/config.toml"

DEFAULT_TARGET_WIDTH=800
DEFAULT_QUALITY=85
DEFAULT_OUTPUT_SUFFIX=""

TARGET_WIDTH=${DEFAULT_TARGET_WIDTH}
QUALITY=${DEFAULT_QUALITY}
OUTPUT_SUFFIX=${DEFAULT_OUTPUT_SUFFIX}
# -----------------------------------------------------------------------------

trim_spaces() {
    local value=$1
    value="${value#"${value%%[![:space:]]*}"}"
    value="${value%"${value##*[![:space:]]}"}"
    printf '%s' "$value"
}

parse_toml_value() {
    local key=$1
    local value

    if [[ ! -f "$CONFIG_FILE" ]]; then
        return 1
    fi

    value=$(awk -v search_key="$key" '
        {
            line = $0
            sub(/^[[:space:]]+/, "", line)
            if (line == "" || line ~ /^#/) {
                next
            }

            split(line, parts, "=")
            current_key = parts[1]
            gsub(/[[:space:]]+$/, "", current_key)
            gsub(/^[[:space:]]+/, "", current_key)

            if (current_key != search_key) {
                next
            }

            value = substr(line, index(line, "=") + 1)
            gsub(/^[[:space:]]+/, "", value)
            sub(/[[:space:]]+#.*/, "", value)
            sub(/[[:space:]]+$/, "", value)

            print value
            exit
        }
    ' "$CONFIG_FILE")

    if [[ -z "$value" ]]; then
        return 1
    fi

    printf '%s' "$value"
}

load_config() {
    local raw_width
    local raw_quality
    local raw_suffix

    raw_width=$(parse_toml_value "target_width" || true)
    if [[ -n "$raw_width" ]]; then
        raw_width=$(trim_spaces "$raw_width")
        if [[ "$raw_width" =~ ^[0-9]+$ && "$raw_width" -gt 0 ]]; then
            TARGET_WIDTH=$raw_width
        else
            echo "WARN: Invalid target_width in ${CONFIG_FILE}; using ${DEFAULT_TARGET_WIDTH}." >&2
        fi
    fi

    raw_quality=$(parse_toml_value "quality" || true)
    if [[ -n "$raw_quality" ]]; then
        raw_quality=$(trim_spaces "$raw_quality")
        if [[ "$raw_quality" =~ ^[0-9]+$ && "$raw_quality" -ge 1 && "$raw_quality" -le 100 ]]; then
            QUALITY=$raw_quality
        else
            echo "WARN: Invalid quality in ${CONFIG_FILE}; using ${DEFAULT_QUALITY}." >&2
        fi
    fi

    raw_suffix=$(parse_toml_value "output_suffix" || true)
    if [[ -n "$raw_suffix" ]]; then
        raw_suffix=$(trim_spaces "$raw_suffix")
        if [[ "$raw_suffix" =~ ^\".*\"$ ]]; then
            raw_suffix=${raw_suffix#\"}
            raw_suffix=${raw_suffix%\"}
            OUTPUT_SUFFIX=$raw_suffix
        else
            echo "WARN: Invalid output_suffix in ${CONFIG_FILE}; expected quoted string. Using default." >&2
        fi
    fi
}

load_config

# Dependency check
if ! command -v cwebp &>/dev/null; then
    notify-send -u critical "convert-to-webp" \
        "❌ 'cwebp' not found.\nInstall it with:  sudo pacman -S libwebp-utils" 2>/dev/null || true
    echo "ERROR: 'cwebp' is not installed. Run: sudo pacman -S libwebp-utils" >&2
    exit 1
fi

if ! command -v convert &>/dev/null; then
    notify-send -u critical "convert-to-webp" \
        "❌ 'convert' (ImageMagick) not found.\nInstall it with:  sudo pacman -S imagemagick" 2>/dev/null || true
    echo "ERROR: 'convert' (ImageMagick) is not installed. Run: sudo pacman -S imagemagick" >&2
    exit 1
fi

if [[ $# -eq 0 ]]; then
    echo "Usage: $(basename "$0") <image1> [image2] ..."
    exit 1
fi

success=0
failed=0

for src in "$@"; do

    # Skip non-files
    if [[ ! -f "$src" ]]; then
        echo "Skipping (not a file): $src"
        (( failed++ )) || true
        continue
    fi

    # Determine output path
    dir="$(dirname "$src")"
    base="$(basename "$src")"
    name="${base%.*}"                            # strip extension
    dest="${dir}/${name}${OUTPUT_SUFFIX}.webp"

    echo "▶ Converting: $src"

    # Step 1: Resize to configured max width (retaining aspect ratio) into a temp PNG
    tmp="$(mktemp /tmp/webp-resize-XXXXXX.png)"
    trap 'rm -f "$tmp"' EXIT

    if ! convert "$src" -resize "${TARGET_WIDTH}>" "$tmp" 2>/dev/null; then
        echo "  ✗ Resize failed for: $src"
        (( failed++ )) || true
        rm -f "$tmp"
        continue
    fi

    # Step 2: Encode to WebP
    if ! cwebp -q "$QUALITY" "$tmp" -o "$dest" 2>/dev/null; then
        echo "  ✗ WebP encoding failed for: $src"
        (( failed++ )) || true
        rm -f "$tmp"
        continue
    fi

    rm -f "$tmp"

    src_size=$(du -sh "$src" 2>/dev/null | cut -f1)
    dst_size=$(du -sh "$dest" 2>/dev/null | cut -f1)
    echo "  ✔ Saved → $dest  ($src_size → $dst_size)"
    (( success++ )) || true

done

# Summary desktop notification
msg="${success} file(s) converted successfully."
[[ $failed -gt 0 ]] && msg+=" ${failed} failed."

notify-send "convert-to-webp" "$msg" 2>/dev/null || true
echo ""
echo "Done. $msg"
