#!/usr/bin/env python3

import copy
from collections import OrderedDict
from typing import Dict, Any, Optional, List, Iterator, Tuple

import torch
import torch.nn as nn
from fbgemm_gpu.split_embedding_configs import SparseType
from fbgemm_gpu.split_table_batched_embeddings_ops import (
    PoolingMode,
    IntNBitTableBatchedEmbeddingBagsCodegen,
    EmbeddingLocation,
)
from torch import Tensor
from torchrec.modules.embedding_configs import (
    EmbeddingBagConfig,
    PoolingType,
    DataType,
    DATA_TYPE_NUM_BITS,
)
from torchrec.modules.embedding_modules import (
    EmbeddingBagCollection as OriginalEmbeddingBagCollection,
)
from torchrec.modules.embedding_modules import EmbeddingBagCollectionInterface
from torchrec.sparse.jagged_tensor import (
    KeyedJaggedTensor,
    KeyedTensor,
)

torch.ops.load_library("//deeplearning/fbgemm/fbgemm_gpu:sparse_ops")


class EmbeddingBagCollection(EmbeddingBagCollectionInterface):
    def __init__(
        self,
        table_name_to_quantized_weights: Dict[str, Tuple[Tensor, Tensor]],
        embedding_configs: List[EmbeddingBagConfig],
        is_weighted: bool,
        device: torch.device,
    ) -> None:
        def to_pooling_mode(pooling_type: PoolingType) -> PoolingMode:
            if pooling_type == PoolingType.SUM:
                return PoolingMode.SUM
            else:
                assert pooling_type == PoolingType.MEAN
                return PoolingMode.MEAN

        def to_sparse_type(data_type: DataType) -> SparseType:
            if data_type == DataType.FP16:
                return SparseType.FP16
            elif data_type == DataType.INT8:
                return SparseType.INT8
            elif data_type == DataType.INT4:
                return SparseType.INT4
            elif data_type == DataType.INT2:
                return SparseType.INT2
            else:
                raise ValueError(f"Invalid DataType {data_type}")

        super().__init__()

        self._is_weighted = is_weighted
        self._embedding_bag_configs: List[EmbeddingBagConfig] = embedding_configs
        self.embedding_bags: nn.ModuleList[nn.Module] = nn.ModuleList()
        for emb_config in self._embedding_bag_configs:
            emb_module = IntNBitTableBatchedEmbeddingBagsCodegen(
                embedding_specs=[
                    (
                        "",
                        emb_config.num_embeddings,
                        emb_config.embedding_dim,
                        to_sparse_type(emb_config.data_type),
                        EmbeddingLocation.HOST
                        if device.type == "cpu"
                        else EmbeddingLocation.DEVICE,
                    )
                ],
                pooling_mode=to_pooling_mode(emb_config.pooling),
                weight_lists=[table_name_to_quantized_weights[emb_config.name]],
                device=device,
            )

            self.embedding_bags.append(emb_module)

    def forward(
        self,
        features: KeyedJaggedTensor,
    ) -> KeyedTensor:
        keys: List[str] = []
        pooled_embeddings: List[Tensor] = []
        length_per_key: List[int] = []
        for emb_config, emb_module in zip(
            self._embedding_bag_configs, self.embedding_bags
        ):
            for feature_name in emb_config.feature_names:
                keys.append(feature_name)

                values = features[feature_name].values()
                offsets = features[feature_name].offsets()
                weights = features[feature_name].weights_or_none()
                pooled_embeddings.append(
                    emb_module(
                        indices=values.int(),
                        offsets=offsets.int(),
                        per_sample_weights=weights,
                    ).float()
                )

                length_per_key.append(emb_config.embedding_dim)

        return KeyedTensor(
            keys=features.keys(),
            values=torch.cat(pooled_embeddings, dim=1),
            length_per_key=length_per_key,
        )

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
        for emb_config, emb_module in zip(
            self._embedding_bag_configs,
            self.embedding_bags,
        ):
            (weight, _) = emb_module.split_embedding_weights(split_scale_shifts=False)[
                0
            ]
            destination[prefix + f"embedding_bags.{emb_config.name}.weight"] = weight
        return destination

    def named_buffers(
        self, prefix: str = "", recurse: bool = True
    ) -> Iterator[Tuple[str, nn.Parameter]]:
        state_dict = self.state_dict(prefix=prefix, keep_vars=True)
        for key, value in state_dict.items():
            yield key, value

    def _get_name(self) -> str:
        return "QuantizedEmbeddingBagCollection"

    @classmethod
    def from_float(
        cls, module: OriginalEmbeddingBagCollection
    ) -> "EmbeddingBagCollection":
        assert hasattr(
            module, "qconfig"
        ), "EmbeddingBagCollection input float module must have qconfig defined"

        def _to_data_type(dtype: torch.dtype) -> DataType:
            if dtype == torch.quint8 or dtype == torch.qint8:
                return DataType.INT8
            elif dtype == torch.quint4 or dtype == torch.qint4:
                return DataType.INT4
            elif dtype == torch.quint2 or dtype == torch.qint2:
                return DataType.INT2
            else:
                raise Exception(f"Invalid data type {dtype}")

        # pyre-ignore [16]
        data_type = _to_data_type(module.qconfig.weight().dtype)
        embedding_bag_configs = copy.deepcopy(module.embedding_bag_configs)
        for config in embedding_bag_configs:
            config.data_type = data_type

        table_name_to_quantized_weights: Dict[str, Tuple[Tensor, Tensor]] = {}
        device = torch.device("cpu")
        for key, tensor in module.state_dict().items():
            # Extract table name from state dict key.
            # e.g. ebc.embedding_bags.t1.weight
            splits = key.split(".")
            assert splits[-1] == "weight"
            table_name = splits[-2]

            num_bits = DATA_TYPE_NUM_BITS[data_type]
            device = tensor.device
            if tensor.is_meta:
                quant_weight = torch.empty(
                    (tensor.shape[0], (tensor.shape[1] * num_bits) // 8),
                    device="meta",
                    dtype=module.qconfig.weight().dtype,
                )
                scale_shift = torch.empty(
                    (tensor.shape[0], 4),
                    device="meta",
                    dtype=module.qconfig.weight().dtype,
                )
            else:
                quant_res = torch.ops.fbgemm.FloatToFusedNBitRowwiseQuantizedSBHalf(
                    tensor, num_bits
                )
                quant_weight, scale_shift = (
                    quant_res[:, :-4],
                    quant_res[:, -4:],
                )
            table_name_to_quantized_weights[table_name] = (quant_weight, scale_shift)

        return cls(
            table_name_to_quantized_weights,
            embedding_bag_configs,
            module.is_weighted,
            device=device,
        )

    @property
    def embedding_bag_configs(
        self,
    ) -> List[EmbeddingBagConfig]:
        return self._embedding_bag_configs

    @property
    def is_weighted(self) -> bool:
        return self._is_weighted
