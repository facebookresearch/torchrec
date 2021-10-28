#!/usr/bin/env python3

import abc
from dataclasses import dataclass, field
from typing import List, Tuple, Optional, Dict, Any

import torch
import torch.distributed as dist
from torch import nn
from torch.distributed._sharding_spec import ShardMetadata
from torchrec.distributed.dist_data import KJTAllToAll
from torchrec.distributed.embedding_types import (
    GroupedEmbeddingConfig,
    BaseEmbeddingLookup,
    SparseFeatures,
    EmbeddingComputeKernel,
    ShardedEmbeddingTable,
    BaseGroupedFeatureProcessor,
    SparseFeaturesList,
)
from torchrec.distributed.types import Awaitable
from torchrec.modules.embedding_configs import (
    PoolingType,
    DataType,
)
from torchrec.sparse.jagged_tensor import KeyedJaggedTensor
from torchrec.types import Multistreamable


@dataclass
class SequenceShardingContext(Multistreamable):
    """
    SequenceEmbeddingAll2all has the same comm pattern as KJTAll2all.
    Stores KJTAll2all context and reuse it in SequenceEmbeddingAll2all.

    features_before_input_dist: stores the original KJT before input dist
    input_splits: stores the input splits of KJT ALl2all
    input_splits: stores the output splits of KJT ALl2all
    unbucketize_permute_tensor: stores the permute order of
        KJT bucketize (forrow-wise sharding only)
    lengths_after_input_dist: stores the KJT length after input dist
    """

    features_before_input_dist: Optional[KeyedJaggedTensor] = None
    input_splits: List[int] = field(default_factory=list)
    output_splits: List[int] = field(default_factory=list)
    unbucketize_permute_tensor: Optional[torch.Tensor] = None
    lengths_after_input_dist: Optional[torch.Tensor] = None

    def record_stream(self, stream: torch.cuda.streams.Stream) -> None:
        if self.features_before_input_dist is not None:
            self.features_before_input_dist.record_stream(stream)
        if self.unbucketize_permute_tensor is not None:
            self.unbucketize_permute_tensor.record_stream(stream)
        if self.lengths_after_input_dist is not None:
            self.lengths_after_input_dist.record_stream(stream)


class SparseFeaturesAllToAllAwaitable(Awaitable[SparseFeatures]):
    def __init__(
        self,
        id_list_features_awaitable: Optional[Awaitable[KeyedJaggedTensor]],
        id_score_list_features_awaitable: Optional[Awaitable[KeyedJaggedTensor]],
    ) -> None:
        super().__init__()
        self._id_list_features_awaitable = id_list_features_awaitable
        self._id_score_list_features_awaitable = id_score_list_features_awaitable

    def wait(self) -> SparseFeatures:
        return SparseFeatures(
            id_list_features=self._id_list_features_awaitable.wait()
            if self._id_list_features_awaitable is not None
            else None,
            id_score_list_features=self._id_score_list_features_awaitable.wait()
            if self._id_score_list_features_awaitable is not None
            else None,
        )


class SparseFeaturesAllToAll(nn.Module):
    def __init__(
        self,
        pg: dist.ProcessGroup,
        id_list_features_per_rank: List[int],
        id_score_list_features_per_rank: List[int],
        device: Optional[torch.device] = None,
        stagger: int = 1,
    ) -> None:
        super().__init__()
        self._id_list_features_all2all = KJTAllToAll(
            pg, id_list_features_per_rank, device, stagger
        )
        self._id_score_list_features_all2all = KJTAllToAll(
            pg, id_score_list_features_per_rank, device, stagger
        )

    def forward(
        self,
        sparse_features: SparseFeatures,
    ) -> Awaitable[SparseFeatures]:
        return SparseFeaturesAllToAllAwaitable(
            id_list_features_awaitable=self._id_list_features_all2all.forward(
                sparse_features.id_list_features
            )
            if sparse_features.id_list_features is not None
            else None,
            id_score_list_features_awaitable=self._id_score_list_features_all2all.forward(
                sparse_features.id_score_list_features
            )
            if sparse_features.id_score_list_features is not None
            else None,
        )


# group tables by DataType, PoolingType, Weighted, and EmbeddingComputeKernel.
def group_tables(
    tables_per_rank: List[List[ShardedEmbeddingTable]],
) -> Tuple[List[List[GroupedEmbeddingConfig]], List[List[GroupedEmbeddingConfig]]]:
    def _group_tables_per_rank(
        embedding_tables: List[ShardedEmbeddingTable],
    ) -> Tuple[List[GroupedEmbeddingConfig], List[GroupedEmbeddingConfig]]:
        grouped_embedding_configs: List[GroupedEmbeddingConfig] = []
        score_grouped_embedding_configs: List[GroupedEmbeddingConfig] = []
        for data_type in DataType:
            for pooling in PoolingType:
                for is_weighted in [True, False]:
                    for has_feature_processor in [True, False]:
                        for compute_kernel in [
                            EmbeddingComputeKernel.DENSE,
                            EmbeddingComputeKernel.SPARSE,
                            EmbeddingComputeKernel.BATCHED_DENSE,
                            EmbeddingComputeKernel.BATCHED_FUSED,
                            EmbeddingComputeKernel.BATCHED_QUANT,
                        ]:
                            global_grouped_tables: List[ShardedEmbeddingTable] = []
                            global_grouped_score_tables: List[
                                ShardedEmbeddingTable
                            ] = []
                            local_grouped_tables: List[ShardedEmbeddingTable] = []
                            local_grouped_score_tables: List[ShardedEmbeddingTable] = []
                            for table in embedding_tables:
                                if table.compute_kernel in [
                                    EmbeddingComputeKernel.BATCHED_FUSED_UVM,
                                    EmbeddingComputeKernel.BATCHED_FUSED_UVM_CACHING,
                                ]:
                                    compute_kernel_type = (
                                        EmbeddingComputeKernel.BATCHED_FUSED
                                    )
                                else:
                                    compute_kernel_type = table.compute_kernel
                                    if (
                                        table.data_type == data_type
                                        and table.pooling == pooling
                                        and table.is_weighted == is_weighted
                                        and table.has_feature_processor
                                        == has_feature_processor
                                        and compute_kernel_type == compute_kernel
                                    ):

                                        # if not empty on the rank, add to local configs
                                        table_not_empty = (
                                            table.local_rows != 0
                                            and table.local_cols != 0
                                        )
                                        if table.is_weighted:
                                            global_grouped_score_tables.append(table)
                                            if table_not_empty:
                                                local_grouped_score_tables.append(table)
                                        else:
                                            global_grouped_tables.append(table)
                                            if table_not_empty:
                                                local_grouped_tables.append(table)
                            if local_grouped_tables:
                                grouped_embedding_configs.append(
                                    GroupedEmbeddingConfig(
                                        data_type=data_type,
                                        pooling=pooling,
                                        is_weighted=is_weighted,
                                        has_feature_processor=has_feature_processor,
                                        compute_kernel=compute_kernel,
                                        global_embedding_tables=global_grouped_tables,
                                        local_embedding_tables=local_grouped_tables,
                                    )
                                )
                            if local_grouped_score_tables:
                                score_grouped_embedding_configs.append(
                                    GroupedEmbeddingConfig(
                                        data_type=data_type,
                                        pooling=pooling,
                                        is_weighted=is_weighted,
                                        has_feature_processor=has_feature_processor,
                                        compute_kernel=compute_kernel,
                                        global_embedding_tables=global_grouped_score_tables,
                                        local_embedding_tables=local_grouped_score_tables,
                                    )
                                )
        return grouped_embedding_configs, score_grouped_embedding_configs

    grouped_embedding_configs_by_rank: List[List[GroupedEmbeddingConfig]] = []
    score_grouped_embedding_configs_by_rank: List[List[GroupedEmbeddingConfig]] = []
    for tables in tables_per_rank:
        (
            grouped_embedding_configs,
            score_grouped_embedding_configs,
        ) = _group_tables_per_rank(tables)
        grouped_embedding_configs_by_rank.append(grouped_embedding_configs)
        score_grouped_embedding_configs_by_rank.append(score_grouped_embedding_configs)
    return (
        grouped_embedding_configs_by_rank,
        score_grouped_embedding_configs_by_rank,
    )


class SparseFeaturesListAwaitable(Awaitable[SparseFeaturesList]):
    def __init__(
        self,
        awaitables: List[Awaitable[SparseFeatures]],
    ) -> None:
        super().__init__()
        self.awaitables = awaitables

    def wait(self) -> SparseFeaturesList:
        return SparseFeaturesList([w.wait() for w in self.awaitables])


class BaseSparseFeaturesDist(abc.ABC, nn.Module):
    """
    Converts input from data-parallel to model-parallel.
    """

    @abc.abstractmethod
    def forward(
        self,
        sparse_features: SparseFeatures,
    ) -> Awaitable[SparseFeatures]:
        pass


class BasePooledEmbeddingDist(abc.ABC, nn.Module):
    """
    Converts output of pooled EmbeddingLookup
    from model-parallel to data-parallel.
    """

    @abc.abstractmethod
    def forward(self, local_embs: torch.Tensor) -> Awaitable[torch.Tensor]:
        pass


class BaseSequenceEmbeddingDist(abc.ABC, nn.Module):
    """
    Converts output of sequence EmbeddingLookup
    from model-parallel to data-parallel.
    """

    pass

    @abc.abstractmethod
    def forward(
        self, sharding_ctx: SequenceShardingContext, local_embs: torch.Tensor
    ) -> Awaitable[torch.Tensor]:
        pass


class EmbeddingSharding(abc.ABC):
    """
    Used to implement different sharding type for EmbeddingBagCollection, e.g. table_wise.
    """

    @abc.abstractmethod
    def create_input_dist(self) -> BaseSparseFeaturesDist:
        pass

    @abc.abstractmethod
    def create_pooled_output_dist(self) -> BasePooledEmbeddingDist:
        pass

    @abc.abstractmethod
    def create_sequence_output_dist(self) -> BaseSequenceEmbeddingDist:
        pass

    @abc.abstractmethod
    def create_lookup(
        self,
        fused_params: Optional[Dict[str, Any]],
        feature_processor: Optional[BaseGroupedFeatureProcessor] = None,
    ) -> BaseEmbeddingLookup:
        pass

    @abc.abstractmethod
    def embedding_dims(self) -> List[int]:
        pass

    @abc.abstractmethod
    def embedding_shard_metadata(self) -> List[Optional[ShardMetadata]]:
        pass

    @abc.abstractmethod
    def embedding_names(self) -> List[str]:
        pass

    @abc.abstractmethod
    def id_list_feature_names(self) -> List[str]:
        pass

    @abc.abstractmethod
    def id_score_list_feature_names(self) -> List[str]:
        pass
