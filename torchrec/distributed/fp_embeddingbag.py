#!/usr/bin/env python3
# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
#
# This source code is licensed under the BSD-style license found in the
# LICENSE file in the root directory of this source tree.

from typing import Dict, Iterator, List, Optional, Type, Union

import torch
from torch import nn

from torchrec.distributed.embedding_types import (
    BaseEmbeddingSharder,
    KJTList,
    ShardedEmbeddingModule,
)
from torchrec.distributed.embeddingbag import (
    EmbeddingBagCollectionContext,
    EmbeddingBagCollectionSharder,
    ShardedEmbeddingBagCollection,
)
from torchrec.distributed.types import (
    Awaitable,
    LazyAwaitable,
    ParameterSharding,
    QuantizedCommCodecs,
    ShardingEnv,
    ShardingType,
)
from torchrec.distributed.utils import append_prefix
from torchrec.modules.feature_processor_ import FeatureProcessorsCollection
from torchrec.modules.fp_embedding_modules import (
    apply_feature_processors_to_kjt,
    FeatureProcessedEmbeddingBagCollection,
)
from torchrec.sparse.jagged_tensor import KeyedJaggedTensor, KeyedTensor


class ShardedFeatureProcessedEmbeddingBagCollection(
    ShardedEmbeddingModule[
        KJTList, List[torch.Tensor], KeyedTensor, EmbeddingBagCollectionContext
    ]
):
    def __init__(
        self,
        module: FeatureProcessedEmbeddingBagCollection,
        table_name_to_parameter_sharding: Dict[str, ParameterSharding],
        ebc_sharder: EmbeddingBagCollectionSharder,
        env: ShardingEnv,
        device: torch.device,
    ) -> None:
        super().__init__()

        self._device = device
        self._env = env

        self._embedding_bag_collection: ShardedEmbeddingBagCollection = (
            ebc_sharder.shard(
                module._embedding_bag_collection,
                table_name_to_parameter_sharding,
                env=env,
                device=device,
            )
        )

        self._lookups: List[nn.Module] = self._embedding_bag_collection._lookups

        self._feature_processors: Union[nn.ModuleDict, FeatureProcessorsCollection]
        if isinstance(module._feature_processors, FeatureProcessorsCollection):
            self._feature_processors = module._feature_processors.to(device)
        else:
            self._feature_processors = torch.nn.ModuleDict(
                {key: fp.to(device) for key, fp in module._feature_processors.items()}
            )

    # pyre-ignore
    def input_dist(
        self, ctx: EmbeddingBagCollectionContext, features: KeyedJaggedTensor
    ) -> Awaitable[Awaitable[KJTList]]:
        return self._embedding_bag_collection.input_dist(ctx, features)

    def apply_feature_processors_to_kjt_list(self, dist_input: KJTList) -> KJTList:
        if isinstance(self._feature_processors, FeatureProcessorsCollection):
            return KJTList(
                [self._feature_processors(features) for features in dist_input]
            )
        else:
            return KJTList(
                [
                    apply_feature_processors_to_kjt(
                        features,
                        self._feature_processors,
                    )
                    for features in dist_input
                ]
            )

    def compute(
        self,
        ctx: EmbeddingBagCollectionContext,
        dist_input: KJTList,
    ) -> List[torch.Tensor]:

        fp_features = self.apply_feature_processors_to_kjt_list(dist_input)
        return self._embedding_bag_collection.compute(ctx, fp_features)

    def output_dist(
        self,
        ctx: EmbeddingBagCollectionContext,
        output: List[torch.Tensor],
    ) -> LazyAwaitable[KeyedTensor]:
        return self._embedding_bag_collection.output_dist(ctx, output)

    def compute_and_output_dist(
        self, ctx: EmbeddingBagCollectionContext, input: KJTList
    ) -> LazyAwaitable[KeyedTensor]:
        fp_features = self.apply_feature_processors_to_kjt_list(input)
        return self._embedding_bag_collection.compute_and_output_dist(ctx, fp_features)

    def create_context(self) -> EmbeddingBagCollectionContext:
        return self._embedding_bag_collection.create_context()

    def sharded_parameter_names(self, prefix: str = "") -> Iterator[str]:
        for fqn, _ in self.named_parameters():
            if "_embedding_bag_collection" in fqn:
                yield append_prefix(prefix, fqn)


class FeatureProcessedEmbeddingBagCollectionSharder(
    BaseEmbeddingSharder[FeatureProcessedEmbeddingBagCollection]
):
    def __init__(
        self,
        ebc_sharder: Optional[EmbeddingBagCollectionSharder] = None,
        qcomm_codecs_registry: Optional[Dict[str, QuantizedCommCodecs]] = None,
    ) -> None:
        super().__init__(qcomm_codecs_registry=qcomm_codecs_registry)
        self._ebc_sharder: EmbeddingBagCollectionSharder = (
            ebc_sharder or EmbeddingBagCollectionSharder(self.qcomm_codecs_registry)
        )

    def shard(
        self,
        module: FeatureProcessedEmbeddingBagCollection,
        params: Dict[str, ParameterSharding],
        env: ShardingEnv,
        device: Optional[torch.device] = None,
    ) -> ShardedFeatureProcessedEmbeddingBagCollection:

        if device is None:
            device = torch.device("cuda")

        return ShardedFeatureProcessedEmbeddingBagCollection(
            module,
            params,
            ebc_sharder=self._ebc_sharder,
            env=env,
            device=device,
        )

    def shardable_parameters(
        self, module: FeatureProcessedEmbeddingBagCollection
    ) -> Dict[str, torch.nn.Parameter]:
        return self._ebc_sharder.shardable_parameters(module._embedding_bag_collection)

    @property
    def module_type(self) -> Type[FeatureProcessedEmbeddingBagCollection]:
        return FeatureProcessedEmbeddingBagCollection

    def sharding_types(self, compute_device_type: str) -> List[str]:
        # No row wise because position weighted FP and RW don't play well together.
        types = [
            ShardingType.DATA_PARALLEL.value,
            ShardingType.TABLE_WISE.value,
            ShardingType.COLUMN_WISE.value,
            ShardingType.TABLE_COLUMN_WISE.value,
        ]

        return types
