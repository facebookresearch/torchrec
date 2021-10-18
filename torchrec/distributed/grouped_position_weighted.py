#!/usr/bin/env python3

from collections import OrderedDict
from typing import Dict, Optional, Iterator, Tuple, Any, List

import torch
import torch.nn as nn
from torchrec.distributed.embedding_types import BaseGroupedFeatureProcessor
from torchrec.distributed.utils import append_prefix
from torchrec.sparse.jagged_tensor import KeyedJaggedTensor


class GroupedPositionWeightedModule(BaseGroupedFeatureProcessor):
    def __init__(
        self, max_feature_lengths: Dict[str, int], device: Optional[torch.device] = None
    ) -> None:
        super().__init__()
        self.max_feature_lengths = max_feature_lengths
        for length in self.max_feature_lengths.values():
            if length <= 0:
                raise
        self.position_weights: nn.ParameterDict = nn.ParameterDict()
        for key, length in max_feature_lengths.items():
            # pyre-ignore [29]
            self.position_weights[key] = nn.Parameter(
                torch.empty([length], device=device).fill_(1.0)
            )
        self.register_buffer(
            "_dummy_weights",
            torch.tensor(
                max(self.max_feature_lengths.values()),
                device=device,
            ).fill_(1.0),
        )

    def forward(self, features: KeyedJaggedTensor) -> KeyedJaggedTensor:
        if features.weights_or_none() is None:
            cat_seq = torch.ops.fbgemm.offsets_range(
                features.offsets().long(), torch.numel(features.values())
            )
        else:
            # for row-wise sharding
            cat_seq = features.weights().long()
        seqs = torch.split(cat_seq, features.length_per_key())
        weights_list = []
        for key, seq in zip(features.keys(), seqs):
            if key in self.max_feature_lengths:
                weights_list.append(
                    torch.gather(self.position_weights[key], dim=0, index=seq)
                )
            else:
                weights_list.append(
                    self._dummy_weights[: self.max_feature_lengths[key]]
                )
        weights = torch.cat(weights_list)

        return KeyedJaggedTensor(
            keys=features.keys(),
            values=features.values(),
            weights=weights,
            lengths=features.lengths(),
            offsets=features.offsets(),
            stride=features.stride(),
            length_per_key=features.length_per_key(),
        )

    def named_parameters(
        self, prefix: str = "", recurse: bool = True
    ) -> Iterator[Tuple[str, nn.Parameter]]:
        # pyre-ignore [29]
        for name, param in self.position_weights.items():
            yield append_prefix(prefix, f"position_weights.{name}"), param

    def named_buffers(
        self, prefix: str = "", recurse: bool = True
    ) -> Iterator[Tuple[str, torch.Tensor]]:
        yield from ()

    def state_dict(
        self,
        destination: Optional[Dict[str, Any]] = None,
        prefix: str = "",
        keep_vars: bool = False,
    ) -> Dict[str, Any]:
        if destination is None:
            destination = OrderedDict()
            # pyre-ignore [16]
            destination._metadata = OrderedDict()
        # pyre-ignore [29]
        for name, param in self.position_weights.items():
            destination[prefix + f"position_weights.{name}"] = param
        return destination

    def sparse_grad_parameter_names(
        self, destination: Optional[List[str]] = None, prefix: str = ""
    ) -> List[str]:
        destination = [] if destination is None else destination
        return destination
