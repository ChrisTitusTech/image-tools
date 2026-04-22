# Vendored from BasicSR (https://github.com/XPixelGroup/BasicSR)
# Apache License 2.0
# Only the three functions needed for RRDBNet inference are included.

import torch
from torch import nn
from torch.nn import init
from torch.nn.modules.batchnorm import _BatchNorm


@torch.no_grad()
def default_init_weights(module_list, scale: float = 1.0, bias_fill: float = 0.0, **kwargs):
    """Initialize network weights (kaiming normal, scaled)."""
    if not isinstance(module_list, list):
        module_list = [module_list]
    for module in module_list:
        for m in module.modules():
            if isinstance(m, nn.Conv2d):
                init.kaiming_normal_(m.weight, **kwargs)
                m.weight.data *= scale
                if m.bias is not None:
                    m.bias.data.fill_(bias_fill)
            elif isinstance(m, nn.Linear):
                init.kaiming_normal_(m.weight, **kwargs)
                m.weight.data *= scale
                if m.bias is not None:
                    m.bias.data.fill_(bias_fill)
            elif isinstance(m, _BatchNorm):
                init.constant_(m.weight, 1)
                if m.bias is not None:
                    m.bias.data.fill_(bias_fill)


def make_layer(basic_block, num_basic_block, **kwarg):
    """Stack `num_basic_block` instances of `basic_block` into an nn.Sequential."""
    layers = [basic_block(**kwarg) for _ in range(num_basic_block)]
    return nn.Sequential(*layers)


def pixel_unshuffle(x, scale):
    """Inverse of PixelShuffle: reduce spatial size, enlarge channel count."""
    b, c, hh, hw = x.size()
    out_channel = c * (scale ** 2)
    assert hh % scale == 0 and hw % scale == 0
    h = hh // scale
    w = hw // scale
    x_view = x.view(b, c, h, scale, w, scale)
    return x_view.permute(0, 1, 3, 5, 2, 4).reshape(b, out_channel, h, w)
