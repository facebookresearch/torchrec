#!/usr/bin/env python3
# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
#
# This source code is licensed under the BSD-style license found in the
# LICENSE file in the root directory of this source tree.

#!/usr/bin/env python3

import copy
import unittest
from typing import List, Tuple

import torch
from torch.distributed._shard.sharding_spec import ShardingSpec
from torchrec.distributed.embedding_types import EmbeddingComputeKernel, ShardingType
from torchrec.distributed.planner import EmbeddingShardingPlanner, Topology
from torchrec.distributed.planner.enumerators import EmbeddingEnumerator
from torchrec.distributed.planner.shard_estimators import (
    EmbeddingPerfEstimator,
    EmbeddingStorageEstimator,
)
from torchrec.distributed.shard import _shard_modules

from torchrec.distributed.test_utils.infer_utils import (
    model_input_to_forward_args,
    prep_inputs,
    quantize,
    TestModelInfo,
    TestQuantEBCSharder,
    TorchTypesModelInputWrapper,
)
from torchrec.distributed.test_utils.test_model import TestSparseNN
from torchrec.distributed.types import (
    ModuleShardingPlan,
    ParameterSharding,
    ShardingEnv,
)
from torchrec.modules.embedding_configs import EmbeddingBagConfig


# pyre-ignore
def assert_close(expected, got) -> None:
    if isinstance(expected, dict):
        for feature, jt_e in expected.items():
            jt_got = got[feature]
            torch.testing.assert_close(jt_e.lengths(), jt_got.lengths())
            torch.testing.assert_close(jt_e.values(), jt_got.values())
            torch.testing.assert_close(jt_e.offsets(), jt_got.offsets())
    else:
        torch.testing.assert_close(expected, got)


def _model(
    num_embeddings: int,
    emb_dim: int,
    world_size: int,
    batch_size: int,
    dense_device: torch.device,
    sparse_device: torch.device,
) -> TestModelInfo:
    topology: Topology = Topology(world_size=world_size, compute_device="cuda")
    mi = TestModelInfo(
        dense_device=dense_device,
        sparse_device=sparse_device,
        num_features=1,
        num_float_features=8,
        num_weighted_features=1,
        topology=topology,
    )

    mi.planner = EmbeddingShardingPlanner(
        topology=topology,
        batch_size=batch_size,
        enumerator=EmbeddingEnumerator(
            topology=topology,
            batch_size=batch_size,
            estimator=[
                EmbeddingPerfEstimator(topology=topology, is_inference=True),
                EmbeddingStorageEstimator(topology=topology),
            ],
        ),
    )

    mi.tables = [
        EmbeddingBagConfig(
            num_embeddings=num_embeddings,
            embedding_dim=emb_dim,
            name="table_" + str(i),
            feature_names=["feature_" + str(i)],
        )
        for i in range(mi.num_features)
    ]

    mi.weighted_tables = [
        EmbeddingBagConfig(
            num_embeddings=num_embeddings,
            embedding_dim=emb_dim,
            name="weighted_table_" + str(i),
            feature_names=["weighted_feature_" + str(i)],
        )
        for i in range(mi.num_weighted_features)
    ]

    mi.model = TorchTypesModelInputWrapper(
        TestSparseNN(
            tables=mi.tables,
            weighted_tables=mi.weighted_tables,
            num_float_features=mi.num_float_features,
            dense_device=dense_device,
            sparse_device=sparse_device,
        )
    )
    mi.model.training = False
    mi.quant_model = quantize(mi.model, inplace=False)
    return mi


def _shard_qebc(
    mi: TestModelInfo,
    sharding_type: ShardingType,
    device: torch.device,
    expected_shards: List[Tuple[Tuple[int, int, int, int], str]],
) -> torch.nn.Module:
    sharder = TestQuantEBCSharder(
        sharding_type=sharding_type.value,
        kernel_type=EmbeddingComputeKernel.QUANT.value,
        shardable_params=[table.name for table in mi.tables],
    )
    # pyre-ignore
    plan = mi.planner.plan(
        mi.quant_model,
        [sharder],
    )
    msp: ModuleShardingPlan = plan.plan["_module.sparse.ebc"]
    # pyre-ignore
    ps: ParameterSharding = msp["table_0"]
    assert ps.sharding_type == sharding_type.value
    assert ps.sharding_spec is not None
    sharding_spec: ShardingSpec = ps.sharding_spec
    # pyre-ignore
    assert len(sharding_spec.shards) == len(expected_shards)
    for shard, ((offset_r, offset_c, size_r, size_c), placement) in zip(
        sharding_spec.shards, expected_shards
    ):
        assert shard.shard_offsets == [offset_r, offset_c]
        assert shard.shard_sizes == [size_r, size_c]
        assert str(shard.placement) == placement

    # We want to leave quant_model unchanged to compare the results with it
    quant_model_copy = copy.deepcopy(mi.quant_model)
    sharded_model = _shard_modules(
        module=quant_model_copy,
        # pyre-ignore
        sharders=[sharder],
        device=device,
        plan=plan,
        # pyre-ignore
        env=ShardingEnv.from_local(world_size=mi.topology.world_size, rank=0),
    )
    return sharded_model


class InferShardingsTest(unittest.TestCase):
    @unittest.skip(
        "TODO(ivankobzarev): re-enable with quant_state_dict_split_scale_shifts"
    )
    def test_rw(self) -> None:
        num_embeddings = 256
        emb_dim = 12
        world_size = 2
        batch_size = 4
        local_device = torch.device("cuda:0")
        mi = _model(
            num_embeddings,
            emb_dim,
            world_size,
            batch_size,
            dense_device=local_device,
            sparse_device=local_device,
        )

        non_sharded_model = mi.quant_model
        num_emb_half = num_embeddings // 2
        sharded_model = _shard_qebc(
            mi,
            sharding_type=ShardingType.ROW_WISE,
            device=local_device,
            expected_shards=[
                ((0, 0, num_emb_half, emb_dim), "rank:0/cuda:0"),
                ((num_emb_half, 0, num_emb_half, emb_dim), "rank:1/cuda:1"),
            ],
        )
        inputs = [
            model_input_to_forward_args(inp.to(local_device))
            for inp in prep_inputs(mi, world_size, batch_size)
        ]

        sharded_model.load_state_dict(non_sharded_model.state_dict())

        sharded_output = sharded_model(*inputs[0])
        non_sharded_output = non_sharded_model(*inputs[0])
        assert_close(sharded_output, non_sharded_output)
