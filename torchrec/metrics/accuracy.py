#!/usr/bin/env python3
# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
#
# This source code is licensed under the BSD-style license found in the
# LICENSE file in the root directory of this source tree.

# pyre-strict

from typing import Any, cast, Dict, List, Optional, Type

import torch
from torchrec.metrics.metrics_namespace import MetricName, MetricNamespace, MetricPrefix
from torchrec.metrics.rec_metric import (
    MetricComputationReport,
    RecMetric,
    RecMetricComputation,
    RecMetricException,
)


THRESHOLD = "threshold"


def compute_accuracy(
    accuracy_sum: torch.Tensor, weighted_num_samples: torch.Tensor
) -> torch.Tensor:
    return torch.where(
        weighted_num_samples == 0.0, 0.0, accuracy_sum / weighted_num_samples
    ).double()


def compute_accuracy_sum(
    labels: torch.Tensor,
    predictions: torch.Tensor,
    weights: torch.Tensor,
    threshold: float = 0.5,
) -> torch.Tensor:
    predictions = predictions.double()
    return torch.sum(weights * ((predictions >= threshold) == labels), dim=-1)


def get_accuracy_states(
    labels: torch.Tensor,
    predictions: torch.Tensor,
    weights: Optional[torch.Tensor],
    threshold: float = 0.5,
) -> torch.Tensor:
    if weights is None:
        weights = torch.ones_like(predictions)

    return torch.stack(
        [
            compute_accuracy_sum(
                labels, predictions, weights, threshold
            ),  # accuracy sum
            torch.sum(weights, dim=-1),  # weighted_num_samples
        ]
    )


class AccuracyMetricComputation(RecMetricComputation):
    r"""
    This class implements the RecMetricComputation for Accuracy.

    The constructor arguments are defined in RecMetricComputation.
    See the docstring of RecMetricComputation for more detail.

    Args:
        threshold (float): If provided, computes accuracy metrics cutting off at
            the specified threshold.
    """

    def __init__(self, *args: Any, threshold: float = 0.5, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.state_names = ["accuracy_sum", "weighted_num_samples"]
        self._add_state(
            self.state_names,
            torch.zeros((len(self.state_names), self._n_tasks), dtype=torch.double),
            add_window_state=True,
            dist_reduce_fx="sum",
            persistent=True,
        )
        self._threshold: float = threshold

    def update(
        self,
        *,
        predictions: Optional[torch.Tensor],
        labels: torch.Tensor,
        weights: Optional[torch.Tensor],
        **kwargs: Dict[str, Any],
    ) -> None:
        if predictions is None:
            raise RecMetricException(
                "Inputs 'predictions' should not be None for AccuracyMetricComputation update"
            )
        num_samples = predictions.shape[-1]
        states = get_accuracy_states(labels, predictions, weights, self._threshold)
        state = getattr(self, self._fused_name)
        state += states
        self._aggregate_window_state(self._fused_name, states, num_samples)

    def _compute(self) -> List[MetricComputationReport]:
        reports = [
            MetricComputationReport(
                name=MetricName.ACCURACY,
                metric_prefix=MetricPrefix.LIFETIME,
                value=compute_accuracy(
                    self.get_state("accuracy_sum"),
                    self.get_state("weighted_num_samples"),
                ),
            ),
            MetricComputationReport(
                name=MetricName.ACCURACY,
                metric_prefix=MetricPrefix.WINDOW,
                value=compute_accuracy(
                    self.get_window_state("accuracy_sum"),
                    self.get_window_state("weighted_num_samples"),
                ),
            ),
        ]
        return reports


class AccuracyMetric(RecMetric):
    _namespace: MetricNamespace = MetricNamespace.ACCURACY
    _computation_class: Type[RecMetricComputation] = AccuracyMetricComputation
