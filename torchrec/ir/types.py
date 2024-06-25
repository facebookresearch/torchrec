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
        # Take the eager embedding module and generate bytes,
        #  and a list of children (fqns) which needs further serialization
        raise NotImplementedError

    @classmethod
    @abc.abstractmethod
    def deserialize(
        cls,
        ir_metadata: torch.Tensor,  # serialized bytes into a tensor
        device: Optional[torch.device] = None,
        unflatten_ep: Optional[nn.Module] = None,  # unflattened ExportedProgram module
    ) -> nn.Module:
        # Take the bytes in the buffer and regenerate the eager embedding module
        raise NotImplementedError

    @classmethod
    @abc.abstractmethod
    def encapsulate_module(cls, module: nn.Module) -> List[str]:
        # Take the eager embedding module and encapsulate the module, including serialization
        # and meta_forward-swapping, then returns a list of children (fqns) which needs further encapsulation
        raise NotImplementedError

    @classmethod
    @abc.abstractmethod
    def decapsulate_module(
        cls, module: nn.Module, device: Optional[torch.device] = None
    ) -> nn.Module:
        # Take the eager embedding module and decapsulate it by removing serialization and meta_forward-swapping
        raise NotImplementedError
