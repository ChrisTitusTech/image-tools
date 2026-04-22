#!/usr/bin/env python3
"""image-resize: aspect-ratio-preserving image resize CLI."""

from __future__ import annotations

import argparse
import math
import re
import sys
import tempfile
from pathlib import Path

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tiff", ".tif"}
DIMENSIONS_PATTERN = re.compile(r"^\s*(\d+)\s*[xX]\s*(\d+)\s*$")


def parse_dimensions(value: str) -> tuple[int, int]:
    """Parse and validate a WIDTHxHEIGHT string."""
    match = DIMENSIONS_PATTERN.fullmatch(value)
    if match is None:
        raise argparse.ArgumentTypeError(
            "dimensions must be in WIDTHxHEIGHT format, for example 1920x1080"
        )

    width = int(match.group(1))
    height = int(match.group(2))
    if width <= 0 or height <= 0:
        raise argparse.ArgumentTypeError("dimensions must be positive integers")
    return width, height


def collect_images(input_path: Path) -> list[Path]:
    """Return a list of supported image files to process."""
    if input_path.is_file():
        if input_path.suffix.lower() not in IMAGE_EXTENSIONS:
            sys.exit(
                f"ERROR: '{input_path}' is not a supported image file.\n"
                f"Supported: {', '.join(sorted(IMAGE_EXTENSIONS))}"
            )
        return [input_path]

    if input_path.is_dir():
        images = sorted(
            path
            for path in input_path.iterdir()
            if path.is_file() and path.suffix.lower() in IMAGE_EXTENSIONS
        )
        if not images:
            sys.exit(f"ERROR: No supported image files found in '{input_path}'.")
        return images

    sys.exit(f"ERROR: '{input_path}' does not exist.")


def fit_dimensions(width: int, height: int, bounds: tuple[int, int]) -> tuple[int, int]:
    """Scale the image to fit within the requested bounds while preserving aspect ratio."""
    max_width, max_height = bounds
    scale = min(max_width / width, max_height / height)
    target_width = max(1, min(max_width, math.floor(width * scale)))
    target_height = max(1, min(max_height, math.floor(height * scale)))

    if target_width == 0 or target_height == 0:
        raise ValueError("calculated image dimensions are invalid")

    return target_width, target_height


def prepare_image_for_save(image, output_format: str):
    """Convert image modes that are incompatible with the original output format."""
    if output_format in {"JPEG", "JPG"}:
        if image.mode not in {"RGB", "L"}:
            if "A" in image.getbands():
                background = image.getchannel("A")
                flattened = image.convert("RGB")
                return flattened, background
            return image.convert("RGB"), None
    return image, None


def save_overwrite(image_path: Path, resized_image, original_format: str | None, exif_data: bytes | None) -> None:
    """Save a resized image by writing to a temp file and replacing the original."""
    output_format = original_format or image_path.suffix.lstrip(".").upper() or "PNG"
    output_format = "JPEG" if output_format == "JPG" else output_format

    prepared_image, _ = prepare_image_for_save(resized_image, output_format)

    save_kwargs: dict[str, object] = {}
    if exif_data:
        save_kwargs["exif"] = exif_data
    if output_format == "JPEG":
        save_kwargs["quality"] = 95
        save_kwargs["optimize"] = True
    elif output_format == "PNG":
        save_kwargs["optimize"] = True

    with tempfile.NamedTemporaryFile(
        dir=image_path.parent,
        prefix=f".{image_path.stem}-",
        suffix=image_path.suffix,
        delete=False,
    ) as handle:
        temp_path = Path(handle.name)

    try:
        prepared_image.save(temp_path, format=output_format, **save_kwargs)
        temp_path.replace(image_path)
    except Exception:
        temp_path.unlink(missing_ok=True)
        raise


def resize_image(image_path: Path, bounds: tuple[int, int]) -> tuple[int, int]:
    """Resize one image in place and return the resulting dimensions."""
    try:
        from PIL import Image, ImageOps, UnidentifiedImageError
    except ImportError as exc:
        sys.exit(f"ERROR: Missing dependency: {exc.name}. Install the package again.")

    try:
        with Image.open(image_path) as image:
            image = ImageOps.exif_transpose(image)
            source_width, source_height = image.size
            target_width, target_height = fit_dimensions(source_width, source_height, bounds)
            resized = image.resize((target_width, target_height), Image.Resampling.LANCZOS)
            save_overwrite(image_path, resized, image.format, image.info.get("exif"))
            return target_width, target_height
    except UnidentifiedImageError as exc:
        raise RuntimeError("could not identify image format") from exc


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="resize",
        description=(
            "Resize an image or a directory of images to fit within WIDTHxHEIGHT while "
            "preserving aspect ratio. Originals are overwritten in place."
        ),
    )
    parser.add_argument(
        "input",
        help="Path to a single image file, or a directory of images.",
    )
    parser.add_argument(
        "dimensions",
        type=parse_dimensions,
        metavar="WIDTHxHEIGHT",
        help="Target bounding box, for example 1920x1080.",
    )

    args = parser.parse_args()

    input_path = Path(args.input).resolve()
    bounds = args.dimensions
    images = collect_images(input_path)

    print(f"Target  : {bounds[0]}x{bounds[1]}")
    print(f"Images  : {len(images)}")
    print("Output  : originals overwritten in place")
    print()

    succeeded = 0
    failed = 0

    for index, image_path in enumerate(images, start=1):
        print(f"[{index}/{len(images)}] {image_path.name}", end="  ", flush=True)
        try:
            target_width, target_height = resize_image(image_path, bounds)
        except Exception as exc:
            print(f"SKIP ({exc})")
            failed += 1
            continue

        print(f"done -> {target_width}x{target_height}")
        succeeded += 1

    print()
    print(f"Finished: {succeeded} resized, {failed} skipped.")

    if failed > 0:
        sys.exit(1)


if __name__ == "__main__":
    main()