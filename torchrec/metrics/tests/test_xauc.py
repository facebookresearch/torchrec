#!/usr/bin/env python3
# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
#
# This source code is licensed under the BSD-style license found in the
# LICENSE file in the root directory of this source tree.

import unittest
from typing import Dict

import torch
from torchrec.metrics.metrics_config import DefaultTaskInfo
from torchrec.metrics.xauc import XAUCMetric


WORLD_SIZE = 4
BATCH_SIZE = 10


def generate_model_output() -> Dict[str, torch._tensor.Tensor]:
    return {
        "predictions": torch.tensor([[0.1, 0.2, 0.3, 0.4, 0.5]]),
        "labels": torch.tensor([[0.2, 0.1, 0.3, 0.5, 0.25]]),
        "weights": torch.tensor([[1.0, 1.0, 1.0, 0.0, 1.0]]),
        "expected_xauc": torch.tensor([0.6667]),
    }


class XAUCMetricTest(unittest.TestCase):
    def setUp(self) -> None:
        self.xauc = XAUCMetric(
            world_size=WORLD_SIZE,
            my_rank=0,
            batch_size=BATCH_SIZE,
            tasks=[DefaultTaskInfo],
        )

    def test_xauc(self) -> None:
        model_output = generate_model_output()
        self.xauc.update(
            predictions={DefaultTaskInfo.name: model_output["predictions"][0]},
            labels={DefaultTaskInfo.name: model_output["labels"][0]},
            weights={DefaultTaskInfo.name: model_output["weights"][0]},
        )
        metric = self.xauc.compute()
        actual_metric = metric[f"xauc-{DefaultTaskInfo.name}|lifetime_xauc"]
        expected_metric = model_output["expected_xauc"]

        torch.testing.assert_close(
            actual_metric,
            expected_metric,
            atol=1e-4,
            rtol=1e-4,
            check_dtype=False,
            equal_nan=True,
            msg=f"Actual: {actual_metric}, Expected: {expected_metric}",
        )
