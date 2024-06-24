#!/usr/bin/env python3
# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
#
# This source code is licensed under the BSD-style license found in the
# LICENSE file in the root directory of this source tree.

# pyre-strict

#!/usr/bin/env python3

import abc
from typing import Any, Dict, List, Optional, Tuple

import torch

from torch import nn


class SerializerInterface(abc.ABC):
    """
    Interface for Serializer classes for torch.export IR.
    """

    @classmethod
    @property
    def module_to_serializer_cls(cls) -> Dict[str, Any]:
        raise NotImplementedError

    @classmethod
    @abc.abstractmethod
    def serialize(
        cls,
        module: nn.Module,
    ) -> Tuple[torch.Tensor, List[str]]:
        # Take the eager embedding module and generate bytes in buffer
        raise NotImplementedError

    @classmethod
    @abc.abstractmethod
    def deserialize(
        cls,
        input: torch.Tensor,
        device: Optional[torch.device] = None,
        unflatten: Optional[nn.Module] = None,
    ) -> nn.Module:
        # Take the bytes in the buffer and regenerate the eager embedding module
        raise NotImplementedError
