# Vendored from Real-ESRGAN (https://github.com/xinntao/Real-ESRGAN)
# BSD 3-Clause License
# Imports updated to use local vendored registry.

from torch import nn
from torch.nn import functional as F

from .registry import ARCH_REGISTRY


@ARCH_REGISTRY.register()
class SRVGGNetCompact(nn.Module):
    """Compact VGG-style network for super-resolution.

    Upsampling is performed in the last layer only; no convolutions on HR space.

    Args:
        num_in_ch (int): Input channels. Default: 3.
        num_out_ch (int): Output channels. Default: 3.
        num_feat (int): Intermediate feature channels. Default: 64.
        num_conv (int): Number of conv layers in the body. Default: 16.
        upscale (int): Upscaling factor. Default: 4.
        act_type (str): Activation — 'relu', 'prelu', or 'leakyrelu'. Default: 'prelu'.
    """

    def __init__(self, num_in_ch=3, num_out_ch=3, num_feat=64,
                 num_conv=16, upscale=4, act_type='prelu'):
        super().__init__()
        self.num_in_ch = num_in_ch
        self.num_out_ch = num_out_ch
        self.num_feat = num_feat
        self.num_conv = num_conv
        self.upscale = upscale
        self.act_type = act_type

        self.body = nn.ModuleList()
        self.body.append(nn.Conv2d(num_in_ch, num_feat, 3, 1, 1))

        def _activation():
            if act_type == 'relu':
                return nn.ReLU(inplace=True)
            elif act_type == 'prelu':
                return nn.PReLU(num_parameters=num_feat)
            elif act_type == 'leakyrelu':
                return nn.LeakyReLU(negative_slope=0.1, inplace=True)
            raise ValueError(f'Unsupported act_type: {act_type}')

        self.body.append(_activation())

        for _ in range(num_conv):
            self.body.append(nn.Conv2d(num_feat, num_feat, 3, 1, 1))
            self.body.append(_activation())

        self.body.append(nn.Conv2d(num_feat, num_out_ch * upscale * upscale, 3, 1, 1))
        self.upsampler = nn.PixelShuffle(upscale)

    def forward(self, x):
        out = x
        for layer in self.body:
            out = layer(out)
        out = self.upsampler(out)
        base = F.interpolate(x, scale_factor=self.upscale, mode='nearest')
        out += base
        return out
