#!/usr/bin/env python3
# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
#
# This source code is licensed under the BSD-style license found in the
# LICENSE file in the root directory of this source tree.

import copy
import unittest

from functools import partial
from typing import Any, Dict, List, Optional

import hypothesis.strategies as st
import torch
import torch.nn as nn

from torchrec.distributed.propagating_async_collective_tensor import all_to_all_single

from torchrec.distributed.test_utils.multi_process import (
    MultiProcessContext,
    MultiProcessTestBase,
)
from torchrec.test_utils import skip_if_asan_class


def _optional_equals(t1: Optional[torch.Tensor], t2: Optional[torch.Tensor]) -> bool:
    if t1 is None:
        return t2 is None
    return t2 is not None and torch.equal(t1, t2)


def _test_propagating_async_collective_tensor(  # noqa C901
    rank: int,
    world_size: int,
    backend: str,
) -> None:
    with MultiProcessContext(rank, world_size, backend, local_size=world_size) as ctx:
        # output will be rank 0 [0,0,0,0 | 2,2,2,2] rank 1 [1,1,1,1 | 3,3,3,3 ]
        if ctx.rank == 0:
            input = torch.tensor(
                [0, 0, 0, 0, 1, 1, 1, 1],
                device=ctx.device,
                dtype=torch.float,
                requires_grad=True,
            )
        else:
            input = torch.tensor(
                [2, 2, 2, 2, 3, 3, 3, 3],
                device=ctx.device,
                dtype=torch.float,
                requires_grad=True,
            )
        input.retain_grad()

        a2a_out = all_to_all_single(
            input, output_split_sizes=[4, 4], input_split_sizes=[4, 4], group=ctx.pg
        )

        print("a2a out", a2a_out)
        twice_a2a_out = a2a_out * 2
        print("twice_a2a_out", twice_a2a_out)
        a2a_split = twice_a2a_out.split([4, 4])
        a2a_split_view = [x.view(2, 2) for x in a2a_split]
        print("a2a_split_view", a2a_split_view)
        a2a_split_cat = torch.cat(a2a_split_view, dim=0)
        print("a2a split cat", a2a_split_cat)
        sum_twice_a2a_out = a2a_split_cat.sum()
        print("sum_twice_a2a_out before backward", sum_twice_a2a_out)
        sum_twice_a2a_out.backward()
        print("input grad ", input.grad)


@skip_if_asan_class
class TestPropagatingAsyncCollectiveTensor(MultiProcessTestBase):
    @unittest.skipIf(
        torch.cuda.device_count() <= 1,
        "Not enough GPUs, this test requires at least two GPUs",
    )
    def test_pact(self) -> None:

        WORLD_SIZE = 2
        self._run_multi_process_test(
            callable=_test_propagating_async_collective_tensor,
            world_size=WORLD_SIZE,
            backend="nccl"
            if (torch.cuda.is_available() and torch.cuda.device_count() >= 2)
            else "gloo",
        )