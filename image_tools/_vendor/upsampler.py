# Vendored from Real-ESRGAN (https://github.com/xinntao/Real-ESRGAN)
# BSD 3-Clause License
# Changes: removed basicsr dependency; model_path must be a local file path
# (download is handled by the caller in main.py).

import math

import cv2
import numpy as np
import torch
from torch import nn
from torch.nn import functional as F


class RealESRGANer:
    """Helper class for upsampling images with RealESRGAN.

    Args:
        scale (int): Upsampling scale factor (usually 2 or 4).
        model_path (str): Path to the local pretrained .pth weights file.
        model (nn.Module): The network (RRDBNet or SRVGGNetCompact).
        tile (int): Crop input into tiles of this size to limit VRAM usage.
            0 = process the full image at once. Default: 0.
        tile_pad (int): Overlap padding between tiles (removes border artifacts).
            Default: 10.
        pre_pad (int): Extra padding added before inference, removed after.
            Default: 0.
        half (bool): Use float16 (faster, less VRAM). Default: False.
        device (torch.device | None): Target device. Auto-selects CUDA/CPU.
        gpu_id (int | None): Specific GPU index for multi-GPU setups.
    """

    def __init__(self, scale: int, model_path: str, model: nn.Module,
                 tile: int = 0, tile_pad: int = 10,
                 pre_pad: int = 0, half: bool = False,
                 device: torch.device | None = None,
                 gpu_id: int | None = None):
        self.scale = scale
        self.tile_size = tile
        self.tile_pad = tile_pad
        self.pre_pad = pre_pad
        self.mod_scale = None
        self.half = half

        if gpu_id is not None:
            self.device = (
                torch.device(f'cuda:{gpu_id}' if torch.cuda.is_available() else 'cpu')
                if device is None else device
            )
        else:
            self.device = (
                torch.device('cuda' if torch.cuda.is_available() else 'cpu')
                if device is None else device
            )

        loadnet = torch.load(model_path, map_location=torch.device('cpu'), weights_only=False)
        if 'params_ema' in loadnet:
            keyname = 'params_ema'
        else:
            keyname = 'params'
        model.load_state_dict(loadnet[keyname], strict=True)

        model.eval()
        self.model = model.to(self.device)
        if self.half:
            self.model = self.model.half()

    def pre_process(self, img):
        """Pre-pad and mod-pad so the image is divisible by the required factor."""
        img = torch.from_numpy(np.transpose(img, (2, 0, 1))).float()
        self.img = img.unsqueeze(0).to(self.device)
        if self.half:
            self.img = self.img.half()

        if self.pre_pad != 0:
            self.img = F.pad(self.img, (0, self.pre_pad, 0, self.pre_pad), 'reflect')

        if self.scale == 2:
            self.mod_scale = 2
        elif self.scale == 1:
            self.mod_scale = 4

        if self.mod_scale is not None:
            self.mod_pad_h, self.mod_pad_w = 0, 0
            _, _, h, w = self.img.size()
            if h % self.mod_scale != 0:
                self.mod_pad_h = self.mod_scale - h % self.mod_scale
            if w % self.mod_scale != 0:
                self.mod_pad_w = self.mod_scale - w % self.mod_scale
            self.img = F.pad(self.img, (0, self.mod_pad_w, 0, self.mod_pad_h), 'reflect')

    def process(self):
        with torch.no_grad():
            self.output = self.model(self.img)

    def tile_process(self):
        """Crop into tiles, process each, stitch back together."""
        batch, channel, height, width = self.img.shape
        output_height = height * self.scale
        output_width = width * self.scale
        output_shape = (batch, channel, output_height, output_width)

        self.output = self.img.new_zeros(output_shape)
        tiles_x = math.ceil(width / self.tile_size)
        tiles_y = math.ceil(height / self.tile_size)

        for y in range(tiles_y):
            for x in range(tiles_x):
                ofs_x = x * self.tile_size
                ofs_y = y * self.tile_size

                input_start_x = ofs_x
                input_end_x = min(ofs_x + self.tile_size, width)
                input_start_y = ofs_y
                input_end_y = min(ofs_y + self.tile_size, height)

                input_start_x_pad = max(input_start_x - self.tile_pad, 0)
                input_end_x_pad = min(input_end_x + self.tile_pad, width)
                input_start_y_pad = max(input_start_y - self.tile_pad, 0)
                input_end_y_pad = min(input_end_y + self.tile_pad, height)

                input_tile_width = input_end_x - input_start_x
                input_tile_height = input_end_y - input_start_y
                tile_idx = y * tiles_x + x + 1
                input_tile = self.img[
                    :, :,
                    input_start_y_pad:input_end_y_pad,
                    input_start_x_pad:input_end_x_pad,
                ]

                try:
                    with torch.no_grad():
                        output_tile = self.model(input_tile)
                except RuntimeError as error:
                    print(f'  Tile {tile_idx}/{tiles_x * tiles_y} error: {error}')
                    raise

                output_start_x = input_start_x * self.scale
                output_end_x = input_end_x * self.scale
                output_start_y = input_start_y * self.scale
                output_end_y = input_end_y * self.scale

                output_start_x_tile = (input_start_x - input_start_x_pad) * self.scale
                output_end_x_tile = output_start_x_tile + input_tile_width * self.scale
                output_start_y_tile = (input_start_y - input_start_y_pad) * self.scale
                output_end_y_tile = output_start_y_tile + input_tile_height * self.scale

                self.output[
                    :, :,
                    output_start_y:output_end_y,
                    output_start_x:output_end_x,
                ] = output_tile[
                    :, :,
                    output_start_y_tile:output_end_y_tile,
                    output_start_x_tile:output_end_x_tile,
                ]

    def post_process(self):
        if self.mod_scale is not None:
            _, _, h, w = self.output.size()
            self.output = self.output[
                :, :,
                0:h - self.mod_pad_h * self.scale,
                0:w - self.mod_pad_w * self.scale,
            ]
        if self.pre_pad != 0:
            _, _, h, w = self.output.size()
            self.output = self.output[
                :, :,
                0:h - self.pre_pad * self.scale,
                0:w - self.pre_pad * self.scale,
            ]
        return self.output

    @torch.no_grad()
    def enhance(self, img, outscale=None, alpha_upsampler='realesrgan'):
        h_input, w_input = img.shape[0:2]

        img = img.astype(np.float32)
        if np.max(img) > 256:  # 16-bit image
            max_range = 65535
        else:
            max_range = 255
        img = img / max_range

        alpha: np.ndarray | None = None
        if len(img.shape) == 2:  # grayscale
            img_mode = 'L'
            img = cv2.cvtColor(img, cv2.COLOR_GRAY2RGB)
        elif img.shape[2] == 4:  # RGBA
            img_mode = 'RGBA'
            alpha = img[:, :, 3]
            img = img[:, :, 0:3]
            img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
            if alpha_upsampler == 'realesrgan':
                alpha = cv2.cvtColor(alpha, cv2.COLOR_GRAY2RGB)  # type: ignore[arg-type]
        else:
            img_mode = 'RGB'
            img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)

        # Process image (without alpha)
        self.pre_process(img)
        if self.tile_size > 0:
            self.tile_process()
        else:
            self.process()
        output_img = self.post_process()
        output_img = output_img.data.squeeze().float().cpu().clamp_(0, 1).numpy()
        output_img = np.transpose(output_img[[2, 1, 0], :, :], (1, 2, 0))
        if img_mode == 'L':
            output_img = cv2.cvtColor(output_img, cv2.COLOR_BGR2GRAY)

        # Process alpha channel if present
        if img_mode == 'RGBA':
            assert alpha is not None  # always set when img_mode == 'RGBA'
            if alpha_upsampler == 'realesrgan':
                self.pre_process(alpha)
                if self.tile_size > 0:
                    self.tile_process()
                else:
                    self.process()
                output_alpha = self.post_process()
                output_alpha = output_alpha.data.squeeze().float().cpu().clamp_(0, 1).numpy()
                output_alpha = np.transpose(output_alpha[[2, 1, 0], :, :], (1, 2, 0))
                output_alpha = cv2.cvtColor(output_alpha, cv2.COLOR_BGR2GRAY)
            else:
                h, w = alpha.shape[0:2]
                output_alpha = cv2.resize(
                    alpha, (w * self.scale, h * self.scale),
                    interpolation=cv2.INTER_LINEAR,
                )

            output_img = cv2.cvtColor(output_img, cv2.COLOR_BGR2BGRA)
            output_img[:, :, 3] = output_alpha

        if max_range == 65535:
            output = (output_img * 65535.0).round().astype(np.uint16)
        else:
            output = (output_img * 255.0).round().astype(np.uint8)

        if outscale is not None and outscale != float(self.scale):
            output = cv2.resize(
                output,
                (int(w_input * outscale), int(h_input * outscale)),
                interpolation=cv2.INTER_LANCZOS4,
            )

        return output, img_mode
