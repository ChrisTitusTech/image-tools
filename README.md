# image-tools

A unified CLI toolkit for image resizing, AI upscaling, and WebP conversion — all installed from one command into one shared virtual environment.

## Tools

| Command | Description |
|---|---|
| `resize` | Resize images to fit within a bounding box while preserving aspect ratio |
| `upscale` | AI upscaling via Real-ESRGAN (x2, x4, anime, and general models) |
| `copy-image` | Copy image content to the clipboard (X11 and Wayland) |
| `convert-to-webp` | Convert images to WebP format using `cwebp` |

Thunar right-click actions are also registered for all three tools.

## Install

```bash
git clone https://github.com/ChrisTitusTech/image-tools.git
cd image-tools
chmod +x install.sh
./install.sh
```

### Options

```text
./install.sh [--system] [--bin-dir DIR] [--skip-thunar]
```

| Flag | Description |
|---|---|
| `--system` | Install to `/opt/image-tools/venv` and `/usr/local/bin` (requires sudo) |
| `--bin-dir DIR` | Override the command install directory |
| `--skip-thunar` | Skip registering Thunar right-click actions |

Default (user) install puts commands in `~/.local/bin` and the venv in `~/.local/share/image-tools/venv`.

## Usage

### resize

```bash
resize image.png 1920x1080
resize ./photos/ 800x600
```

Originals are overwritten in place.

### upscale

```bash
upscale image.png
upscale image.png --model x4plus-anime --scale 2 --tile 512
upscale ./photos/ --model general-x4v3
```

Output is written to an `upscale/` subfolder next to the source. Available models:

| Model | Description |
|---|---|
| `x4plus` | General images, 4× upscale (default) |
| `x2plus` | General images, 2× upscale |
| `x4plus-anime` | Anime / illustrations, 4× upscale |
| `animevideo` | Anime video frames, 4× upscale (tiny model) |
| `general-x4v3` | General scenes, 4× upscale (small, fast) |

Model weights are downloaded automatically on first use.

### convert-to-webp

Triggered via the Thunar right-click action. Requires `cwebp` (from `webp`) and ImageMagick to be installed.

Default settings are stored in `~/.config/webp-convert/config.toml` (created automatically on first install).

### copy-image

```bash
copy-image image.png
copy-image photo.jpg
```

Copies the image content (not the file path) to the clipboard as PNG so it can be pasted directly into any app (GIMP, Slack, browsers, etc.).

- On **X11** — requires `xclip` (`sudo apt install xclip` / `sudo pacman -S xclip`)
- On **Wayland** — requires `wl-copy` (`sudo apt install wl-clipboard` / `sudo pacman -S wl-clipboard`)

All image formats supported by Pillow (PNG, JPEG, WebP, BMP, TIFF, GIF) are automatically converted to PNG before copying.

A Thunar right-click action **"Copy Image to Clipboard"** is also registered.

## Dependencies

- **resize**: Python ≥ 3.9, Pillow ≥ 10
- **upscale**: Python ≥ 3.9, PyTorch ≥ 2.0, torchvision ≥ 0.15, opencv-python ≥ 4.8
- **copy-image**: Python ≥ 3.9, Pillow ≥ 10; `xclip` (X11) or `wl-copy` (Wayland)
- **convert-to-webp**: `cwebp`, ImageMagick (`convert`)

## Project layout

```
image_tools/
  resize.py        ← resize CLI
  upscale.py       ← upscale CLI
  clipboard.py     ← copy-image CLI
  _vendor/         ← vendored Real-ESRGAN / BasicSR inference code
convert-to-webp.sh
resize-selected.sh
upscale-selected.sh
copy-selected.sh
install.sh
pyproject.toml
```
