#!/usr/bin/env python3
"""copy-image: Copy image content to the Linux clipboard (X11 or Wayland)."""

from __future__ import annotations

import argparse
import io
import os
import shutil
import subprocess
import sys
from pathlib import Path

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tiff", ".tif", ".gif"}


def detect_backend() -> str:
    """Return 'wayland' or 'x11' based on the current display session."""
    if os.environ.get("WAYLAND_DISPLAY"):
        if shutil.which("wl-copy"):
            return "wayland"
        print(
            "WARNING: Wayland session detected but wl-copy not found. "
            "Install wl-clipboard and try again.",
            file=sys.stderr,
        )
        sys.exit(1)

    if os.environ.get("DISPLAY"):
        if shutil.which("xclip"):
            return "x11"
        print(
            "WARNING: X11 session detected but xclip not found. "
            "Install xclip and try again.",
            file=sys.stderr,
        )
        sys.exit(1)

    print(
        "ERROR: No display session detected. "
        "Neither WAYLAND_DISPLAY nor DISPLAY is set.",
        file=sys.stderr,
    )
    sys.exit(1)


def image_to_png_bytes(path: Path) -> bytes:
    """Open any supported image format and return PNG-encoded bytes."""
    try:
        from PIL import Image
    except ImportError:
        print("ERROR: Pillow is not installed.", file=sys.stderr)
        sys.exit(1)

    with Image.open(path) as img:
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        return buf.getvalue()


def copy_to_clipboard(png_bytes: bytes, backend: str) -> None:
    if backend == "wayland":
        subprocess.run(
            ["wl-copy", "--type", "image/png"],
            input=png_bytes,
            check=True,
        )
    else:
        subprocess.run(
            ["xclip", "-selection", "clipboard", "-t", "image/png"],
            input=png_bytes,
            check=True,
        )


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="copy-image",
        description=(
            "Copy the content of an image file to the clipboard. "
            "Supports X11 (via xclip) and Wayland (via wl-copy). "
            "The image is converted to PNG before copying so any format can be pasted."
        ),
    )
    parser.add_argument(
        "input",
        help="Path to an image file to copy to the clipboard.",
    )
    args = parser.parse_args()

    path = Path(args.input).expanduser().resolve()

    if not path.exists():
        print(f"ERROR: File not found: {path}", file=sys.stderr)
        sys.exit(1)

    if not path.is_file():
        print(f"ERROR: Not a file: {path}", file=sys.stderr)
        sys.exit(1)

    if path.suffix.lower() not in IMAGE_EXTENSIONS:
        print(
            f"ERROR: Unsupported file type '{path.suffix}'. "
            f"Supported: {', '.join(sorted(IMAGE_EXTENSIONS))}",
            file=sys.stderr,
        )
        sys.exit(1)

    backend = detect_backend()
    png_bytes = image_to_png_bytes(path)
    copy_to_clipboard(png_bytes, backend)

    print(f"Copied {path.name} to clipboard ({len(png_bytes):,} bytes as PNG).")


if __name__ == "__main__":
    main()
