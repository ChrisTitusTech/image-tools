# image-tools

A unified CLI toolkit for image resizing, AI upscaling, WebP conversion, and social video conversion - all installed from one command into one shared virtual environment.

## Tools

| Command | Description |
|---|---|
| `resize` | Resize images to fit within a bounding box while preserving aspect ratio |
| `upscale` | AI upscaling via Real-ESRGAN (x2, x4, anime, and general models) |
| `copy-image` | Copy image content to the clipboard (X11 and Wayland) |
| `convert-to-webp` | Convert images to WebP format using `cwebp` |
| `convert-to-social-video` | Convert videos to social-ready MP4 with HandBrakeCLI, progress, and ETA |

Thunar right-click actions are registered for all tools. **Convert to Social Video** appears for video files, including multiple selections.

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
When system packages are missing, the installer uses `sudo` to install them with `apt`, `dnf`, or `pacman`.

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

### convert-to-social-video

Right-click one or more videos in Thunar and choose **Convert to Social Video**.
Rerun `./install.sh` after updating this repository, then restart Thunar to load the action.

```bash
convert-to-social-video "my video.mov" clip.mkv
# Terminal-only progress (no desktop required):
convert-to-social-video --no-gui "my video.mov"
```

The progress dialog shows overall batch progress, current file, encoding percentage,
and HandBrake's estimated time remaining for that file. Scanning initially shows
"estimating time"; final MP4 optimization may continue after the encode ETA reaches
zero. Cancel stops the current conversion and the queue, removes partial output,
and retains completed files. Individual failures are reported at the end while
other selected files continue.

Output is saved beside each original as `name-social.mp4`, with numbered suffixes
if needed. Originals and existing outputs are never overwritten. Any video format
HandBrake can decode is accepted; unreadable or unsupported files show an error.

Defaults use X's encoding recommendations as a starting point, with no duration
or output-size cap:

- Fast-start MP4, H.264 High profile level 4.0, 8-bit 4:2:0, constant 30 fps.
- 6 Mbps target video bitrate, 8 Mbps maximum, closed GOP up to 2 seconds.
- First audio track encoded as AAC-LC at 128 kbps, 48 kHz, stereo/mono;
  silent videos remain silent. Subtitle tracks are not copied.
- Fit landscape within 1920x1080, square within 1080x1080, and portrait within
  1080x1900, preserving aspect ratio without cropping or upscaling. Phone rotation metadata
  is applied to the picture before sizing. A 9:16 source
  becomes approximately 1068x1900 because X's general help caps portrait height
  at 1900. Dimensions are rounded to even pixels.
- BT.709 color conversion (including HDR tone mapping) and deinterlacing when detected.
- Preserve the entire video regardless of duration or output size. Nothing is
  silently trimmed. Reject aspect ratios outside X's 1:2.39 to 2.39:1 range
  rather than stretching the picture.

These settings provide broadly supported web video encoding; upload eligibility
still depends on each platform, post type, and account. X's API, advertising, and
Premium upload rules differ, so this is not a guarantee for every social upload route.
Sources: [X video upload limits](https://help.x.com/en/using-x/x-videos),
[X encoding recommendations](https://help.x.com/en/using-twitter/media-studio-faqs.html),
and [HandBrake CLI reference](https://handbrake.fr/docs/en/latest/cli/command-line-reference.html).

The installer installs HandBrakeCLI when missing. Fedora requires a repository
providing `HandBrake-cli` (usually RPM Fusion); configure that repository yourself
if DNF cannot find the package. No additional Python dependencies are required.

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
- **convert-to-webp**: `cwebp`, ImageMagick (`magick` or `convert`)
- **convert-to-social-video**: Python >= 3.9, `HandBrakeCLI`; Zenity for desktop progress
- **desktop actions**: Zenity and `notify-send`

## Project layout

```
image_tools/
  resize.py        ← resize CLI
  upscale.py       ← upscale CLI
  clipboard.py     ← copy-image CLI
  social_video.py  <- HandBrake conversion and progress CLI
  _vendor/         ← vendored Real-ESRGAN / BasicSR inference code
convert-to-webp.sh
resize-selected.sh
upscale-selected.sh
copy-selected.sh
install.sh
pyproject.toml
```
