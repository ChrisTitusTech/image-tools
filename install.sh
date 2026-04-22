#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)

# Tool locations
RESIZE_WRAPPER_SOURCE="${SCRIPT_DIR}/resize-selected.sh"
UPSCALE_WRAPPER_SOURCE="${SCRIPT_DIR}/upscale-selected.sh"
WEBP_CONVERTER_SOURCE="${SCRIPT_DIR}/convert-to-webp.sh"
COPY_WRAPPER_SOURCE="${SCRIPT_DIR}/copy-selected.sh"

# Install names
RESIZE_WRAPPER_NAME="resize-selected"
UPSCALE_WRAPPER_NAME="upscale-selected"
WEBP_COMMAND_NAME="convert-to-webp"
COPY_WRAPPER_NAME="copy-selected"

# Thunar metadata
THUNAR_CONFIG_DIR="${XDG_CONFIG_HOME:-$HOME/.config}/Thunar"
THUNAR_UCA_FILE="${THUNAR_CONFIG_DIR}/uca.xml"

ACTION_RESIZE_ID="thunar-image-resize"
ACTION_RESIZE_NAME="Resize Image"
ACTION_RESIZE_DESCRIPTION="Resize selected image files while preserving aspect ratio."
ACTION_RESIZE_ICON="image-x-generic"

ACTION_UPSCALE_ID="thunar-image-upscale"
ACTION_UPSCALE_NAME="Upscale Image (Real-ESRGAN)"
ACTION_UPSCALE_DESCRIPTION="Upscale selected image files with Real-ESRGAN."
ACTION_UPSCALE_ICON="image-x-generic"

ACTION_WEBP_ID="thunar-webp-convert"
ACTION_WEBP_NAME="Convert to WebP"
ACTION_WEBP_DESCRIPTION="Convert selected image files to WebP using your config settings."
ACTION_WEBP_ICON="image-x-generic"

ACTION_COPY_ID="thunar-image-copy-clipboard"
ACTION_COPY_NAME="Copy Image to Clipboard"
ACTION_COPY_DESCRIPTION="Copy selected image content to the clipboard (X11 or Wayland)."
ACTION_COPY_ICON="edit-copy"

WEBP_CONFIG_DIR="${XDG_CONFIG_HOME:-$HOME/.config}/webp-convert"
WEBP_CONFIG_FILE="${WEBP_CONFIG_DIR}/config.toml"
DEFAULT_WEBP_CONFIG_CONTENT=$(cat <<'EOF'
target_width = 800
quality = 85
output_suffix = ""
EOF
)

usage() {
    cat <<EOF
Usage: $(basename "$0") [--system] [--bin-dir DIR] [--skip-thunar]

Installs image-resize, image-upscale, and WebP conversion tools together.

Options:
  --system       Install to /opt/image-tools/venv and use /usr/local/bin.
  --bin-dir DIR  Install commands/wrappers to a specific bin directory.
  --skip-thunar  Skip writing Thunar custom actions.
  -h, --help     Show this help text.
EOF
}

xml_escape() {
    sed \
        -e 's/&/\&amp;/g' \
        -e 's/</\&lt;/g' \
        -e 's/>/\&gt;/g' <<<"$1"
}

remove_existing_action() {
    local input_file=$1
    local output_file=$2
    local action_id=$3

    awk -v action_id="$action_id" '
        function flush_action() {
            if (buffer != "" && !drop_buffer) {
                printf "%s", buffer
            }
            buffer = ""
            drop_buffer = 0
            in_action = 0
        }

        BEGIN {
            in_action = 0
            buffer = ""
            drop_buffer = 0
        }

        !in_action {
            if ($0 ~ /<action>/) {
                in_action = 1
                buffer = $0 ORS
            } else {
                print
            }
            next
        }

        {
            buffer = buffer $0 ORS
            if ($0 ~ ("<unique-id>" action_id "</unique-id>")) {
                drop_buffer = 1
            }
            if ($0 ~ /<\/action>/) {
                flush_action()
            }
        }

        END {
            if (in_action) {
                flush_action()
            }
        }
    ' "$input_file" > "$output_file"
}

write_uca_file_with_action() {
    local destination=$1
    local action_id=$2
    local action_command=$3
    local action_description=$4
    local action_name=$5
    local action_icon=$6

    cat > "$destination" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<actions>
  <action>
    <icon>${action_icon}</icon>
    <name>${action_name}</name>
    <submenu></submenu>
    <unique-id>${action_id}</unique-id>
    <command>${action_command}</command>
    <description>${action_description}</description>
    <patterns>*</patterns>
    <startup-notify/>
    <directories/>
    <audio-files/>
    <image-files/>
    <other-files/>
    <text-files/>
    <video-files/>
  </action>
</actions>
EOF
}

update_thunar_action() {
    local action_id=$1
    local action_name=$2
    local action_description=$3
    local action_icon=$4
    local installed_command=$5

    local escaped_command
    local escaped_description
    local escaped_name
    local escaped_icon
    local tmp_clean
    local tmp_final

    escaped_command=$(xml_escape "\"${installed_command}\" %F")
    escaped_description=$(xml_escape "$action_description")
    escaped_name=$(xml_escape "$action_name")
    escaped_icon=$(xml_escape "$action_icon")

    install -d -m 755 "$THUNAR_CONFIG_DIR"

    if [[ ! -f "$THUNAR_UCA_FILE" ]]; then
        write_uca_file_with_action "$THUNAR_UCA_FILE" "$action_id" "$escaped_command" "$escaped_description" "$escaped_name" "$escaped_icon"
        chmod 644 "$THUNAR_UCA_FILE"
        return
    fi

    if ! grep -q '<actions>' "$THUNAR_UCA_FILE" || ! grep -q '</actions>' "$THUNAR_UCA_FILE"; then
        echo "ERROR: ${THUNAR_UCA_FILE} does not look like a valid Thunar custom actions file." >&2
        exit 1
    fi

    tmp_clean=$(mktemp)
    tmp_final=$(mktemp)

    remove_existing_action "$THUNAR_UCA_FILE" "$tmp_clean" "$action_id"

    awk \
        -v action_id="$action_id" \
        -v action_command="$escaped_command" \
        -v action_description="$escaped_description" \
        -v action_name="$escaped_name" \
        -v action_icon="$escaped_icon" '
            BEGIN {
                inserted = 0
                action_block = "  <action>\n" \
                    "    <icon>" action_icon "</icon>\n" \
                    "    <name>" action_name "</name>\n" \
                    "    <submenu></submenu>\n" \
                    "    <unique-id>" action_id "</unique-id>\n" \
                    "    <command>" action_command "</command>\n" \
                    "    <description>" action_description "</description>\n" \
                    "    <patterns>*</patterns>\n" \
                    "    <startup-notify/>\n" \
                    "    <directories/>\n" \
                    "    <audio-files/>\n" \
                    "    <image-files/>\n" \
                    "    <other-files/>\n" \
                    "    <text-files/>\n" \
                    "    <video-files/>\n" \
                    "  </action>\n"
            }

            /<\/actions>/ && !inserted {
                printf "%s", action_block
                inserted = 1
            }

            {
                print
            }

            END {
                if (!inserted) {
                    exit 1
                }
            }
        ' "$tmp_clean" > "$tmp_final"

    install -m 644 "$tmp_final" "$THUNAR_UCA_FILE"
    rm -f "$tmp_clean" "$tmp_final"
}

ensure_webp_config() {
    install -d -m 755 "$WEBP_CONFIG_DIR"

    if [[ ! -f "$WEBP_CONFIG_FILE" ]]; then
        printf '%s\n' "$DEFAULT_WEBP_CONFIG_CONTENT" > "$WEBP_CONFIG_FILE"
        chmod 644 "$WEBP_CONFIG_FILE"
        echo "Created config file: ${WEBP_CONFIG_FILE}"
    fi
}

validate_sources() {
    local missing=0

    for required in \
        "$SCRIPT_DIR/pyproject.toml" \
        "$SCRIPT_DIR/image_tools/resize.py" \
        "$SCRIPT_DIR/image_tools/upscale.py" \
        "$SCRIPT_DIR/image_tools/clipboard.py" \
        "$RESIZE_WRAPPER_SOURCE" \
        "$UPSCALE_WRAPPER_SOURCE" \
        "$WEBP_CONVERTER_SOURCE" \
        "$COPY_WRAPPER_SOURCE"; do
        if [[ ! -f "$required" ]]; then
            echo "ERROR: Missing required file: $required" >&2
            missing=1
        fi
    done

    if [[ $missing -eq 1 ]]; then
        exit 1
    fi
}

install_python_tools() {
    local system_install=$1
    local install_dir=$2
    local venv_dir

    if ! command -v python3 >/dev/null 2>&1; then
        echo "ERROR: python3 not found." >&2
        exit 1
    fi

    if [[ $system_install -eq 1 ]]; then
        if [[ $EUID -ne 0 ]]; then
            echo "ERROR: --system requires root privileges (use sudo)." >&2
            exit 1
        fi
        venv_dir="/opt/image-tools/venv"
    else
        venv_dir="${XDG_DATA_HOME:-$HOME/.local/share}/image-tools/venv"
    fi

    install -d -m 755 "$(dirname "$venv_dir")"
    python3 -m venv "$venv_dir"
    "$venv_dir/bin/python" -m pip install --upgrade pip
    "$venv_dir/bin/python" -m pip install --upgrade "$SCRIPT_DIR[upscale]"

    install -d -m 755 "$install_dir"
    install -m 755 "$venv_dir/bin/resize" "$install_dir/resize"
    install -m 755 "$venv_dir/bin/upscale" "$install_dir/upscale"
    install -m 755 "$venv_dir/bin/copy-image" "$install_dir/copy-image"

    echo "Installed Python CLIs in venv: $venv_dir"
}

install_shell_tools() {
    local install_dir=$1

    install -d -m 755 "$install_dir"
    install -m 755 "$RESIZE_WRAPPER_SOURCE" "$install_dir/$RESIZE_WRAPPER_NAME"
    install -m 755 "$UPSCALE_WRAPPER_SOURCE" "$install_dir/$UPSCALE_WRAPPER_NAME"
    install -m 755 "$WEBP_CONVERTER_SOURCE" "$install_dir/$WEBP_COMMAND_NAME"
    install -m 755 "$COPY_WRAPPER_SOURCE" "$install_dir/$COPY_WRAPPER_NAME"
}

main() {
    local system_install=0
    local bin_dir_override=
    local skip_thunar=0
    local install_dir=

    while [[ $# -gt 0 ]]; do
        case "$1" in
            --system)
                system_install=1
                shift
                ;;
            --bin-dir)
                if [[ $# -lt 2 ]]; then
                    echo "ERROR: --bin-dir requires a value." >&2
                    exit 1
                fi
                bin_dir_override=$2
                shift 2
                ;;
            --skip-thunar)
                skip_thunar=1
                shift
                ;;
            -h|--help)
                usage
                exit 0
                ;;
            *)
                echo "ERROR: Unknown option: $1" >&2
                usage >&2
                exit 1
                ;;
        esac
    done

    validate_sources

    if [[ -n "$bin_dir_override" ]]; then
        install_dir=$bin_dir_override
    elif [[ $system_install -eq 1 || $EUID -eq 0 ]]; then
        install_dir=/usr/local/bin
    else
        install_dir="${HOME}/.local/bin"
    fi

    install_python_tools "$system_install" "$install_dir"
    install_shell_tools "$install_dir"
    ensure_webp_config

    if [[ $skip_thunar -eq 0 ]]; then
        update_thunar_action "$ACTION_RESIZE_ID" "$ACTION_RESIZE_NAME" "$ACTION_RESIZE_DESCRIPTION" "$ACTION_RESIZE_ICON" "$install_dir/$RESIZE_WRAPPER_NAME"
        update_thunar_action "$ACTION_UPSCALE_ID" "$ACTION_UPSCALE_NAME" "$ACTION_UPSCALE_DESCRIPTION" "$ACTION_UPSCALE_ICON" "$install_dir/$UPSCALE_WRAPPER_NAME"
        update_thunar_action "$ACTION_WEBP_ID" "$ACTION_WEBP_NAME" "$ACTION_WEBP_DESCRIPTION" "$ACTION_WEBP_ICON" "$install_dir/$WEBP_COMMAND_NAME"
        update_thunar_action "$ACTION_COPY_ID" "$ACTION_COPY_NAME" "$ACTION_COPY_DESCRIPTION" "$ACTION_COPY_ICON" "$install_dir/$COPY_WRAPPER_NAME"
    fi

    cat <<EOF

Install complete.

Commands:
  resize
  upscale
  copy-image
  $RESIZE_WRAPPER_NAME
  $UPSCALE_WRAPPER_NAME
  $WEBP_COMMAND_NAME
  $COPY_WRAPPER_NAME

Thunar actions:
  $ACTION_RESIZE_NAME
  $ACTION_UPSCALE_NAME
  $ACTION_WEBP_NAME
  $ACTION_COPY_NAME

If '$install_dir' is not on your PATH, add it before using the commands.
Restart Thunar if it is currently open so it reloads custom actions.
EOF
}

main "$@"
