#!/usr/bin/env python3
# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
#
# This source code is licensed under the BSD-style license found in the
# LICENSE file in the root directory of this source tree.

# pyre-strict

import math
import unittest
from typing import List

import hypothesis.strategies as st

import torch
from hypothesis import given, settings
from torch import nn
from torchrec.distributed.embedding_types import EmbeddingComputeKernel
from torchrec.distributed.embeddingbag import EmbeddingBagCollectionSharder
from torchrec.distributed.planner.planners import EmbeddingShardingPlanner
from torchrec.distributed.planner.stats import (
    _calc_max_chi_divergence,
    _calc_max_kl_divergence,
    _chi_divergence,
    _kl_divergence,
    _normalize_float,
    _normalize_int,
    _total_distance,
    _total_variation,
    EmbeddingStats,
    NoopEmbeddingStats,
)
from torchrec.distributed.planner.types import Topology
from torchrec.distributed.test_utils.test_model import TestSparseNN
from torchrec.distributed.types import ModuleSharder, ShardingType
from torchrec.modules.embedding_configs import EmbeddingBagConfig


class TWvsRWSharder(EmbeddingBagCollectionSharder, ModuleSharder[nn.Module]):
    def sharding_types(self, compute_device_type: str) -> List[str]:
        return [ShardingType.ROW_WISE.value, ShardingType.TABLE_WISE.value]

    def compute_kernels(
        self, sharding_type: str, compute_device_type: str
    ) -> List[str]:
        return [EmbeddingComputeKernel.FUSED.value]


class TestEmbeddingStats(unittest.TestCase):
    def setUp(self) -> None:
        compute_device = "cuda"
        self.topology = Topology(
            world_size=2, hbm_cap=1024 * 1024 * 2, compute_device=compute_device
        )
        tables = [
            EmbeddingBagConfig(
                num_embeddings=100,
                embedding_dim=64,
                name="table_" + str(i),
                feature_names=["feature_" + str(i)],
            )
            for i in range(4)
        ]
        self.model = TestSparseNN(tables=tables, sparse_device=torch.device("meta"))

    def test_embedding_stats_runs(self) -> None:
        planner = EmbeddingShardingPlanner(topology=self.topology)
        _ = planner.plan(module=self.model, sharders=[TWvsRWSharder()])
        self.assertEqual(len(planner._stats), 1)
        stats_data = planner._stats[0]
        assert isinstance(stats_data, EmbeddingStats)
        stats: List[str] = stats_data._stats_table
        self.assertTrue(isinstance(stats, list))
        self.assertTrue(stats[0].startswith("####"))

    def test_empty_embedding_stats_runs(self) -> None:
        planner = EmbeddingShardingPlanner(topology=self.topology, stats=[])
        _ = planner.plan(module=self.model, sharders=[TWvsRWSharder()])
        self.assertEqual(len(planner._stats), 0)

    def test_noop_embedding_stats_runs(self) -> None:
        planner = EmbeddingShardingPlanner(
            topology=self.topology, stats=NoopEmbeddingStats()
        )
        _ = planner.plan(module=self.model, sharders=[TWvsRWSharder()])
        self.assertEqual(len(planner._stats), 1)

    def test_embedding_stats_output_with_top_hbm_usage(self) -> None:
        planner = EmbeddingShardingPlanner(topology=self.topology)
        _ = planner.plan(module=self.model, sharders=[TWvsRWSharder()])
        self.assertEqual(len(planner._stats), 1)
        stats_data = planner._stats[0]
        assert isinstance(stats_data, EmbeddingStats)
        stats: List[str] = stats_data._stats_table
        self.assertTrue(isinstance(stats, list))
        top_hbm_usage_keyword = "Top HBM Memory Usage Estimation:"
        self.assertTrue(any(top_hbm_usage_keyword in row for row in stats))
        top_hbm_mem_usage = None
        for row in stats:
            if top_hbm_usage_keyword in row:
                top_hbm_mem_usage = float(row.split(" ")[6])
        self.assertIsNotNone(top_hbm_mem_usage)

    def test_normalize_float(self) -> None:
        p = [2.0, 2.0]
        self.assertEqual(_normalize_float(p), [0.5, 0.5])

    def test_normalize_int(self) -> None:
        p = [2, 2]
        self.assertEqual(_normalize_int(p), [0.5, 0.5])

    def test_total_variation(self) -> None:
        p_1 = [0.5, 0.5]
        self.assertEqual(_total_variation(p_1), 0.0)

        p_2 = [0.0, 1.0]
        self.assertEqual(_total_variation(p_2), 0.5)

    def test_total_distance(self) -> None:
        p_1 = [0.5, 0.5]
        self.assertEqual(_total_distance(p_1), 0.0)

        p_2 = [0.0, 1.0]
        self.assertEqual(_total_distance(p_2), 1.0)

    def test_chi_divergence(self) -> None:
        p_1 = [0.5, 0.5]
        self.assertEqual(_chi_divergence(p_1), 0.0)

        p_2 = [0.0, 1.0]
        self.assertEqual(_chi_divergence(p_2), 1.0)

    def test_kl_divergence(self) -> None:
        p_1 = [0.5, 0.5]
        self.assertEqual(_kl_divergence(p_1), 0.0)

        p_2 = [0.1, 0.9]
        self.assertAlmostEqual(_kl_divergence(p_2), 0.368, 3)

    # pyre-ignore
    @given(
        N=st.integers(min_value=10, max_value=200),
    )
    @settings(max_examples=4, deadline=None)
    def test_kl_divergence_upper_bound(self, N: int) -> None:
        # Generate most imbalanced distribution
        normalized_p = [
            1.0,
        ] + [
            0.0
        ] * (N - 1)
        N = len(normalized_p)
        self.assertEqual(_kl_divergence(normalized_p), _calc_max_kl_divergence(N))

    # pyre-ignore
    @given(
        N=st.integers(min_value=10, max_value=200),
        alpha=st.floats(min_value=1.0, max_value=5.0),
    )
    @settings(max_examples=4, deadline=None)
    def test_chi_divergence_upper_bound(self, N: int, alpha: float) -> None:
        # Generate most imbalanced distribution
        normalized_p = [
            1.0,
        ] + [
            0.0
        ] * (N - 1)
        N = len(normalized_p)

        self.assertTrue(
            math.isclose(
                _chi_divergence(normalized_p, alpha),
                _calc_max_chi_divergence(N, alpha),
                abs_tol=1e-10,
            )
        )
