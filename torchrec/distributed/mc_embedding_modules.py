#!/usr/bin/env python3
# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
#
# This source code is licensed under the BSD-style license found in the
# LICENSE file in the root directory of this source tree.

import logging
from typing import Dict, Iterator, List, Optional, Tuple, Type, TypeVar, Union

import torch
from torch.autograd.profiler import record_function
from torchrec.distributed.embedding import (
    EmbeddingCollectionSharder,
    ShardedEmbeddingCollection,
)

from torchrec.distributed.embedding_types import (
    BaseEmbeddingSharder,
    EmbeddingComputeKernel,
    KJTList,
    ShardedEmbeddingModule,
)
from torchrec.distributed.embeddingbag import (
    EmbeddingBagCollectionSharder,
    ShardedEmbeddingBagCollection,
)
from torchrec.distributed.mc_modules import (
    ManagedCollisionCollectionSharder,
    ShardedManagedCollisionCollection,
)
from torchrec.distributed.types import (
    Awaitable,
    LazyAwaitable,
    Multistreamable,
    NoWait,
    ParameterSharding,
    QuantizedCommCodecs,
    ShardingEnv,
)
from torchrec.distributed.utils import append_prefix
from torchrec.modules.embedding_modules import (
    EmbeddingBagCollection,
    EmbeddingCollection,
)
from torchrec.modules.mc_embedding_modules import (
    BaseManagedCollisionEmbeddingCollection,
    ManagedCollisionEmbeddingBagCollection,
    ManagedCollisionEmbeddingCollection,
)
from torchrec.sparse.jagged_tensor import KeyedJaggedTensor, KeyedTensor


logger: logging.Logger = logging.getLogger(__name__)


ShrdCtx = TypeVar("ShrdCtx", bound=Multistreamable)


class BaseShardedManagedCollisionEmbeddingCollection(
    ShardedEmbeddingModule[
        KJTList,
        List[torch.Tensor],
        Tuple[LazyAwaitable[KeyedTensor], LazyAwaitable[Optional[KeyedJaggedTensor]]],
        ShrdCtx,
    ]
):
    def __init__(
        self,
        module: Union[
            ManagedCollisionEmbeddingBagCollection, ManagedCollisionEmbeddingCollection
        ],
        table_name_to_parameter_sharding: Dict[str, ParameterSharding],
        e_sharder: Union[EmbeddingBagCollectionSharder, EmbeddingCollectionSharder],
        mc_sharder: ManagedCollisionCollectionSharder,
        # TODO - maybe we need this to manage unsharded/sharded consistency/state consistency
        env: ShardingEnv,
        device: torch.device,
    ) -> None:
        super().__init__()

        self._device = device
        self._env = env

        if isinstance(module, ManagedCollisionEmbeddingBagCollection):
            assert isinstance(e_sharder, EmbeddingBagCollectionSharder)
            assert isinstance(module._embedding_module, EmbeddingBagCollection)
            self.bagged: bool = True

            self._embedding_module: ShardedEmbeddingBagCollection = e_sharder.shard(
                module._embedding_module,
                table_name_to_parameter_sharding,
                env=env,
                device=device,
            )
        else:
            assert isinstance(e_sharder, EmbeddingCollectionSharder)
            assert isinstance(module._embedding_module, EmbeddingCollection)
            self.bagged: bool = False

            self._embedding_module: ShardedEmbeddingCollection = e_sharder.shard(
                module._embedding_module,
                table_name_to_parameter_sharding,
                env=env,
                device=device,
            )
        # TODO: This is a hack since _embedding_bag_collection doesn't need input
        # dist, so eliminating it so all fused a2a will ignore it.
        self._embedding_module._has_uninitialized_input_dist = False
        self._managed_collision_collection: ShardedManagedCollisionCollection = mc_sharder.shard(
            module._managed_collision_collection,
            table_name_to_parameter_sharding,
            env=env,
            device=device,
            # pyre-ignore
            sharding_type_to_sharding=self._embedding_module._sharding_type_to_sharding,
        )
        self._return_remapped_features: bool = module._return_remapped_features

        # pyre-ignore
        self._table_to_tbe_and_index = {}
        for lookup in self._embedding_module._lookups:
            for emb_module in lookup._emb_modules:
                for table_idx, table in enumerate(emb_module._config.embedding_tables):
                    self._table_to_tbe_and_index[table.name] = (
                        emb_module._emb_module,
                        torch.tensor([table_idx], dtype=torch.int, device=self._device),
                    )
        self._buffer_ids: torch.Tensor = torch.tensor(
            [0], device=self._device, dtype=torch.int
        )

    # pyre-ignore
    def input_dist(
        self,
        ctx: ShrdCtx,
        features: KeyedJaggedTensor,
        force_insert: bool = False,
    ) -> Awaitable[Awaitable[KJTList]]:
        # TODO: resolve incompatiblity with different contexts
        return self._managed_collision_collection.input_dist(
            # pyre-fixme [6]
            ctx,
            features,
            force_insert,
        )

    def _evict(self, evictions_per_table: Dict[str, Optional[torch.Tensor]]) -> None:
        for table, evictions_indices_for_table in evictions_per_table.items():
            if evictions_indices_for_table is not None:
                (tbe, logical_table_ids) = self._table_to_tbe_and_index[table]
                pruned_indices_offsets = torch.tensor(
                    [0, evictions_indices_for_table.shape[0]],
                    dtype=torch.long,
                    device=self._device,
                )
                logger.info(
                    f"Evicting {evictions_indices_for_table.numel()} ids from {table}"
                )
                with torch.no_grad():
                    # embeddings, and optimizer state will be reset
                    tbe.reset_embedding_weight_momentum(
                        pruned_indices=evictions_indices_for_table.long(),
                        pruned_indices_offsets=pruned_indices_offsets,
                        logical_table_ids=logical_table_ids,
                        buffer_ids=self._buffer_ids,
                    )

                    if self.bagged:
                        table_weight_param = (
                            self._embedding_module.embedding_bags.get_parameter(
                                f"{table}.weight"
                            )
                        )
                    else:
                        table_weight_param = (
                            self._embedding_module.embeddings.get_parameter(
                                f"{table}.weight"
                            )
                        )

                    init_fn = self._embedding_module._table_name_to_config[
                        table
                    ].init_fn

                    # Set evicted indices to original init_fn instead of all zeros
                    table_weight_param[evictions_indices_for_table] = init_fn(
                        table_weight_param[evictions_indices_for_table]
                    )

    def compute(
        self,
        ctx: ShrdCtx,
        dist_input: KJTList,
    ) -> List[torch.Tensor]:
        with record_function("## compute:mcc ##"):
            remapped_kjt = self._managed_collision_collection.compute(
                # pyre-fixme [6]
                ctx,
                dist_input,
            )
            evictions_per_table = self._managed_collision_collection.evict()

            self._evict(evictions_per_table)
            ctx.remapped_kjt = remapped_kjt
            ctx.evictions_per_table = evictions_per_table

            # pyre-ignore
            return self._embedding_module.compute(ctx, remapped_kjt)

    # pyre-ignore
    def output_dist(
        self,
        ctx: ShrdCtx,
        output: List[torch.Tensor],
    ) -> Tuple[LazyAwaitable[KeyedTensor], LazyAwaitable[Optional[KeyedJaggedTensor]]]:

        ebc_awaitable = self._embedding_bag_collection.output_dist(ctx, output)

        if self._return_remapped_features:
            kjt_awaitable = self._managed_collision_collection.output_dist(
                # pyre-fixme [6]
                ctx,
                # pyre-ignore [16]
                ctx.remapped_kjt,
            )
        else:
            kjt_awaitable = NoWait(None)

        # pyre-ignore
        return ebc_awaitable, kjt_awaitable

    def sharded_parameter_names(self, prefix: str = "") -> Iterator[str]:
        for fqn, _ in self.named_parameters():
            yield append_prefix(prefix, fqn)
        for fqn, _ in self.named_buffers():
            yield append_prefix(prefix, fqn)


M = TypeVar("M", bound=BaseManagedCollisionEmbeddingCollection)


class BaseManagedCollisionEmbeddingCollectionSharder(BaseEmbeddingSharder[M]):
    def __init__(
        self,
        e_sharder: Union[EmbeddingBagCollectionSharder, EmbeddingCollectionSharder],
        mc_sharder: ManagedCollisionCollectionSharder,
        qcomm_codecs_registry: Optional[Dict[str, QuantizedCommCodecs]] = None,
    ) -> None:
        super().__init__(qcomm_codecs_registry=qcomm_codecs_registry)
        self._e_sharder: Union[
            EmbeddingBagCollectionSharder, EmbeddingCollectionSharder
        ] = e_sharder
        self._mc_sharder: ManagedCollisionCollectionSharder = mc_sharder

    def shardable_parameters(
        self, module: BaseManagedCollisionEmbeddingCollection
    ) -> Dict[str, torch.nn.Parameter]:
        # pyre-ignore
        return self._e_sharder.shardable_parameters(module._embedding_module)

    def compute_kernels(
        self,
        sharding_type: str,
        compute_device_type: str,
    ) -> List[str]:
        return [EmbeddingComputeKernel.FUSED.value]

    def sharding_types(self, compute_device_type: str) -> List[str]:
        return list(
            set.intersection(
                set(self._e_sharder.sharding_types(compute_device_type)),
                set(self._mc_sharder.sharding_types(compute_device_type)),
            )
        )
