#!/usr/bin/env python3
"""image-upscale: Easy image upscaling via Real-ESRGAN."""

import argparse
import sys
import urllib.request
from pathlib import Path

# Supported input image extensions
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tiff", ".tif"}

# Cache directory for model weights (~/.cache/image-upscale/weights/)
CACHE_DIR = Path.home() / ".cache" / "image-upscale" / "weights"

# Model registry: name -> config
MODELS = {
    "x4plus": {
        "description": "General images, 4x upscale (default, best quality)",
        "arch": "rrdbnet",
        "num_block": 23,
        "scale": 4,
        "filename": "RealESRGAN_x4plus.pth",
        "url": "https://github.com/xinntao/Real-ESRGAN/releases/download/v0.1.0/RealESRGAN_x4plus.pth",
    },
    "x2plus": {
        "description": "General images, 2x upscale",
        "arch": "rrdbnet",
        "num_block": 23,
        "scale": 2,
        "filename": "RealESRGAN_x2plus.pth",
        "url": "https://github.com/xinntao/Real-ESRGAN/releases/download/v0.2.1/RealESRGAN_x2plus.pth",
    },
    "x4plus-anime": {
        "description": "Anime / illustrations, 4x upscale (smaller, faster)",
        "arch": "rrdbnet",
        "num_block": 6,
        "scale": 4,
        "filename": "RealESRGAN_x4plus_anime_6B.pth",
        "url": "https://github.com/xinntao/Real-ESRGAN/releases/download/v0.2.2.4/RealESRGAN_x4plus_anime_6B.pth",
    },
    "animevideo": {
        "description": "Anime video frames, 4x upscale (tiny model)",
        "arch": "srvgg",
        "num_conv": 16,
        "scale": 4,
        "filename": "realesr-animevideov3.pth",
        "url": "https://github.com/xinntao/Real-ESRGAN/releases/download/v0.2.5.0/realesr-animevideov3.pth",
    },
    "general-x4v3": {
        "description": "General scenes, 4x upscale (small, fast)",
        "arch": "srvgg",
        "num_conv": 32,
        "scale": 4,
        "filename": "realesr-general-x4v3.pth",
        "url": "https://github.com/xinntao/Real-ESRGAN/releases/download/v0.2.5.0/realesr-general-x4v3.pth",
    },
}


def download_weight(url: str, dest: Path) -> None:
    """Download a model weight file with a progress indicator."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    print(f"  Downloading model weights to {dest} ...")

    def _progress(block_num, block_size, total_size):
        if total_size > 0:
            pct = min(100, block_num * block_size * 100 // total_size)
            print(f"\r  Progress: {pct}%", end="", flush=True)

    urllib.request.urlretrieve(url, dest, _progress)
    print()  # newline after progress


def build_upsampler(model_cfg: dict, tile: int, use_fp32: bool):
    """Construct and return a RealESRGANer instance for the given model config."""
    from image_tools._vendor.upsampler import RealESRGANer

    weight_path = CACHE_DIR / model_cfg["filename"]
    if not weight_path.exists():
        print("Model weights not found locally.")
        download_weight(model_cfg["url"], weight_path)

    scale = model_cfg["scale"]
    arch = model_cfg["arch"]

    if arch == "rrdbnet":
        from image_tools._vendor.rrdbnet_arch import RRDBNet
        model = RRDBNet(
            num_in_ch=3,
            num_out_ch=3,
            num_feat=64,
            num_block=model_cfg["num_block"],
            num_grow_ch=32,
            scale=scale,
        )
    else:  # srvgg
        from image_tools._vendor.srvgg_arch import SRVGGNetCompact
        model = SRVGGNetCompact(
            num_in_ch=3,
            num_out_ch=3,
            num_feat=64,
            num_conv=model_cfg["num_conv"],
            upscale=scale,
            act_type="prelu",
        )

    upsampler = RealESRGANer(
        scale=scale,
        model_path=str(weight_path),
        model=model,
        tile=tile,
        tile_pad=10,
        pre_pad=0,
        half=not use_fp32,
    )
    return upsampler


def collect_images(input_path: Path) -> list[Path]:
    """Return a list of image files to process."""
    if input_path.is_file():
        if input_path.suffix.lower() not in IMAGE_EXTENSIONS:
            sys.exit(f"ERROR: '{input_path}' is not a supported image file.\n"
                     f"Supported: {', '.join(sorted(IMAGE_EXTENSIONS))}")
        return [input_path]

    if input_path.is_dir():
        images = sorted(
            p for p in input_path.iterdir()
            if p.is_file() and p.suffix.lower() in IMAGE_EXTENSIONS
        )
        if not images:
            sys.exit(f"ERROR: No supported image files found in '{input_path}'.")
        return images

    sys.exit(f"ERROR: '{input_path}' does not exist.")


def output_path_for(image: Path, out_dir: Path) -> Path:
    """Return the output path as PNG, preserving original suffix to avoid collisions."""
    # e.g. photo.jpg -> upscale/photo.jpg.png, photo.png -> upscale/photo.png
    if image.suffix.lower() == ".png":
        return out_dir / image.name
    return out_dir / (image.name + ".png")


def main():
    parser = argparse.ArgumentParser(
        prog="upscale",
        description="Upscale images using Real-ESRGAN. Output is written to an 'upscale/' subfolder.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="\n".join(
            ["Available models:"]
            + [f"  {k:16s} {v['description']}" for k, v in MODELS.items()]
        ),
    )
    parser.add_argument(
        "input",
        help="Path to a single image file, or a directory of images.",
    )
    parser.add_argument(
        "--model",
        choices=list(MODELS.keys()),
        default="x4plus",
        metavar="MODEL",
        help=(
            "Model to use for upscaling. "
            f"Choices: {', '.join(MODELS)}. Default: x4plus"
        ),
    )
    parser.add_argument(
        "--scale",
        type=float,
        default=None,
        metavar="N",
        help="Output scale factor (default: matches model scale). "
             "You can use a non-integer, e.g. 3.0 with the x4 model.",
    )
    parser.add_argument(
        "--tile",
        type=int,
        default=0,
        metavar="SIZE",
        help="Tile size for VRAM-limited GPUs (e.g. 512). 0 = process full image. Default: 0",
    )
    parser.add_argument(
        "--fp32",
        action="store_true",
        help="Use float32 instead of float16. Slower but works on CPU and older GPUs.",
    )

    args = parser.parse_args()

    input_path = Path(args.input).resolve()
    model_cfg = MODELS[args.model]
    out_scale = args.scale if args.scale is not None else float(model_cfg["scale"])

    # Collect images
    images = collect_images(input_path)

    # Determine output directory
    if input_path.is_file():
        out_dir = input_path.parent / "upscale"
    else:
        out_dir = input_path / "upscale"

    out_dir.mkdir(parents=True, exist_ok=True)

    print(f"Model   : {args.model} — {model_cfg['description']}")
    print(f"Scale   : {out_scale}x")
    print(f"Images  : {len(images)}")
    print(f"Output  : {out_dir}")
    if args.tile:
        print(f"Tile    : {args.tile}px")
    print()

    # Load model (deferred import so --help works without torch installed)
    upsampler = build_upsampler(model_cfg, tile=args.tile, use_fp32=args.fp32)

    try:
        import cv2
    except ImportError:
        sys.exit("ERROR: 'opencv-python' is not installed.")

    succeeded = 0
    failed = 0

    for idx, img_path in enumerate(images, start=1):
        print(f"[{idx}/{len(images)}] {img_path.name}", end="  ", flush=True)

        img = cv2.imread(str(img_path), cv2.IMREAD_UNCHANGED)
        if img is None:
            print("SKIP (could not read file)")
            failed += 1
            continue

        try:
            output, _ = upsampler.enhance(img, outscale=out_scale)
        except RuntimeError as exc:
            if "CUDA out of memory" in str(exc):
                print("\nERROR: GPU out of memory. Try --tile 512 or --fp32.")
                sys.exit(1)
            print(f"SKIP (error: {exc})")
            failed += 1
            continue

        dest = output_path_for(img_path, out_dir)
        cv2.imwrite(str(dest), output)
        print("done")
        succeeded += 1

    print()
    print(f"Finished: {succeeded} upscaled, {failed} skipped.")
    print(f"Output folder: {out_dir}")


if __name__ == "__main__":
    main()
