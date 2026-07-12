"""Model definitions for transfer learning across several backbones.

Supports full fine-tuning (not just a frozen backbone). Each backbone is loaded
with ImageNet-pretrained weights and its final classification layer is replaced
with a fresh dropout + linear head sized to our number of classes.

Helpers here also:
  * freeze / unfreeze the backbone (for two-phase training), and
  * split parameters into "backbone" vs "head" groups so the fine-tune phase can
    use a lower learning rate on the pretrained backbone (discriminative LR).
"""
from __future__ import annotations

from typing import Callable, Dict, List, Tuple

import torch.nn as nn
from torchvision import models

# Registry: arch name -> (constructor, default-weights enum, head attribute name).
# The head attribute is the module whose final Linear we replace and whose
# parameters form the "head" group.
_BACKBONES: Dict[str, Tuple[Callable, object, str]] = {
    "efficientnet_b0": (
        models.efficientnet_b0,
        models.EfficientNet_B0_Weights.DEFAULT,
        "classifier",
    ),
    "mobilenet_v3_large": (
        models.mobilenet_v3_large,
        models.MobileNet_V3_Large_Weights.DEFAULT,
        "classifier",
    ),
    "mobilenet_v3_small": (
        models.mobilenet_v3_small,
        models.MobileNet_V3_Small_Weights.DEFAULT,
        "classifier",
    ),
    "resnet50": (
        models.resnet50,
        models.ResNet50_Weights.DEFAULT,
        "fc",
    ),
}

AVAILABLE_ARCHS = tuple(_BACKBONES.keys())


def build_model(arch: str, num_classes: int, dropout: float = 0.3) -> nn.Module:
    """Create a pretrained backbone with a fresh classifier head.

    Args:
        arch: one of ``AVAILABLE_ARCHS``.
        num_classes: number of target classes.
        dropout: dropout probability in the new head.
    """
    if arch not in _BACKBONES:
        raise ValueError(f"Unknown arch '{arch}'. Choose from {AVAILABLE_ARCHS}.")

    ctor, weights, head_attr = _BACKBONES[arch]
    model = ctor(weights=weights)

    head = getattr(model, head_attr)
    if isinstance(head, nn.Sequential):
        # e.g. EfficientNet/MobileNet: classifier ends in a Linear.
        in_features = head[-1].in_features
        head[-1] = nn.Sequential(nn.Dropout(p=dropout), nn.Linear(in_features, num_classes))
    else:
        # e.g. ResNet: fc is a single Linear.
        in_features = head.in_features
        setattr(model, head_attr, nn.Sequential(nn.Dropout(p=dropout),
                                                 nn.Linear(in_features, num_classes)))

    # Stash the head attribute name so param-grouping helpers can find it.
    model._head_attr = head_attr  # type: ignore[attr-defined]
    return model


def _head_param_ids(model: nn.Module) -> set:
    head = getattr(model, model._head_attr)  # type: ignore[attr-defined]
    return {id(p) for p in head.parameters()}


def split_params(model: nn.Module) -> Tuple[List[nn.Parameter], List[nn.Parameter]]:
    """Return (backbone_params, head_params)."""
    head_ids = _head_param_ids(model)
    head_params = [p for p in model.parameters() if id(p) in head_ids]
    backbone_params = [p for p in model.parameters() if id(p) not in head_ids]
    return backbone_params, head_params


def set_backbone_trainable(model: nn.Module, trainable: bool) -> None:
    """Freeze (False) or unfreeze (True) every non-head parameter."""
    head_ids = _head_param_ids(model)
    for p in model.parameters():
        if id(p) not in head_ids:
            p.requires_grad = trainable
