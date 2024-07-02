#!/usr/bin/env python3
# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
#
# This source code is licensed under the BSD-style license found in the
# LICENSE file in the root directory of this source tree.

# pyre-strict

import json
from typing import Any, Dict, List, Optional, Tuple, Type

import torch

from torch import nn
from torchrec.ir.schema import (
    EBCMetadata,
    EmbeddingBagConfigMetadata,
    FPEBCMetadata,
    PositionWeightedModuleCollectionMetadata,
    PositionWeightedModuleMetadata,
)

from torchrec.ir.types import SerializerInterface
from torchrec.ir.utils import logging
from torchrec.modules.embedding_configs import DataType, EmbeddingBagConfig, PoolingType
from torchrec.modules.embedding_modules import EmbeddingBagCollection
from torchrec.modules.feature_processor_ import (
    FeatureProcessor,
    FeatureProcessorsCollection,
    PositionWeightedModule,
    PositionWeightedModuleCollection,
)
from torchrec.modules.fp_embedding_modules import FeatureProcessedEmbeddingBagCollection
from torchrec.sparse.jagged_tensor import KeyedJaggedTensor, KeyedTensor


logger: logging.Logger = logging.getLogger(__name__)


def embedding_bag_config_to_metadata(
    table_config: EmbeddingBagConfig,
) -> EmbeddingBagConfigMetadata:
    return EmbeddingBagConfigMetadata(
        num_embeddings=table_config.num_embeddings,
        embedding_dim=table_config.embedding_dim,
        name=table_config.name,
        data_type=table_config.data_type.value,
        feature_names=table_config.feature_names,
        weight_init_max=table_config.weight_init_max,
        weight_init_min=table_config.weight_init_min,
        need_pos=table_config.need_pos,
        pooling=table_config.pooling.value,
    )


def embedding_metadata_to_config(
    table_config: EmbeddingBagConfigMetadata,
) -> EmbeddingBagConfig:
    return EmbeddingBagConfig(
        num_embeddings=table_config.num_embeddings,
        embedding_dim=table_config.embedding_dim,
        name=table_config.name,
        data_type=DataType(table_config.data_type),
        feature_names=table_config.feature_names,
        weight_init_max=table_config.weight_init_max,
        weight_init_min=table_config.weight_init_min,
        need_pos=table_config.need_pos,
        pooling=PoolingType(table_config.pooling),
    )


def get_deserialized_device(
    config_device: Optional[str], device: Optional[torch.device]
) -> Optional[torch.device]:
    if config_device:
        original_device = torch.device(config_device)
        if device is None:
            device = original_device
        elif original_device.type != device.type:
            logger.warning(
                f"deserialized device={device} overrides the original device={original_device}"
            )
    return device


def ebc_meta_forward(
    ebc: EmbeddingBagCollection,
    features: KeyedJaggedTensor,
) -> KeyedTensor:
    batch_size = features.stride()
    dim = sum(ebc._lengths_per_embedding)
    arg_list = [
        features.values(),
        features.weights_or_none(),
        features.lengths_or_none(),
        features.offsets_or_none(),
    ]  # if want to include the weights: `+ [bag.weight for bag in self.embedding_bags.values()]`
    output = torch.ops.torchrec.ir_custom_op(arg_list, batch_size, dim)
    return KeyedTensor(
        keys=ebc._embedding_names,
        values=output,
        length_per_key=ebc._lengths_per_embedding,
    )


def fpebc_meta_forward(
    fpebc: FeatureProcessedEmbeddingBagCollection,
    features: KeyedJaggedTensor,
) -> KeyedTensor:
    batch_size = features.stride()
    ebc = fpebc._embedding_bag_collection
    dim = sum(ebc._lengths_per_embedding)
    arg_list = [
        features.values(),
        features.weights_or_none(),
        features.lengths_or_none(),
        features.offsets_or_none(),
    ]  # if want to include the weights: `+ [bag.weight for bag in self.embedding_bags.values()]`
    output = torch.ops.torchrec.ir_custom_op(arg_list, batch_size, dim)
    return KeyedTensor(
        keys=ebc._embedding_names,
        values=output,
        length_per_key=ebc._lengths_per_embedding,
    )


class JsonSerializer(SerializerInterface):
    """
    Serializer for torch.export IR using json.
    """

    module_to_serializer_cls: Dict[str, Type["JsonSerializer"]] = {}
    _module_cls: Optional[Type[nn.Module]] = None
    _children: Optional[List[str]] = None

    @classmethod
    def children(cls, module: nn.Module) -> List[str]:
        return [] if not cls._children else cls._children

    @classmethod
    def serialize_to_dict(cls, module: nn.Module) -> Dict[str, Any]:
        raise NotImplementedError()

    @classmethod
    def deserialize_from_dict(
        cls,
        metadata_dict: Dict[str, Any],
        device: Optional[torch.device] = None,
        unflatten_ep: Optional[nn.Module] = None,
    ) -> nn.Module:
        raise NotImplementedError()

    @classmethod
    def serialize(
        cls,
        module: nn.Module,
    ) -> Tuple[torch.Tensor, List[str]]:
        typename = type(module).__name__
        serializer = cls.module_to_serializer_cls.get(typename)
        if serializer is None:
            raise ValueError(
                f"Expected typename to be one of {list(cls.module_to_serializer_cls.keys())}, got {typename}"
            )
        assert issubclass(serializer, JsonSerializer)
        assert serializer._module_cls is not None
        if not isinstance(module, serializer._module_cls):
            raise ValueError(
                f"Expected module to be of type {serializer._module_cls.__name__}, "
                f"got {type(module)}"
            )
        metadata_dict = serializer.serialize_to_dict(module)
        raw_dict = {"typename": typename, "metadata_dict": metadata_dict}
        ir_metadata_tensor = torch.frombuffer(
            json.dumps(raw_dict).encode(), dtype=torch.uint8
        )
        return ir_metadata_tensor, serializer.children(module)

    @classmethod
    def deserialize(
        cls,
        ir_metadata: torch.Tensor,
        device: Optional[torch.device] = None,
        unflatten_ep: Optional[nn.Module] = None,
    ) -> nn.Module:
        raw_bytes = ir_metadata.numpy().tobytes()
        raw_dict = json.loads(raw_bytes.decode())
        typename = raw_dict["typename"]
        if typename not in cls.module_to_serializer_cls:
            raise ValueError(
                f"Expected typename to be one of {list(cls.module_to_serializer_cls.keys())}, got {typename}"
            )
        serializer = cls.module_to_serializer_cls[typename]
        assert issubclass(serializer, JsonSerializer)
        module = serializer.deserialize_from_dict(
            raw_dict["metadata_dict"], device, unflatten_ep
        )

        if serializer._module_cls is None:
            raise ValueError(
                "Must assign a nn.Module to class static variable _module_cls"
            )
        if not isinstance(module, serializer._module_cls):
            raise ValueError(
                f"Expected module to be of type {serializer._module_cls.__name__}, got {type(module)}"
            )
        return module

    @classmethod
    def swap_meta_forward(cls, module: nn.Module) -> None:
        pass

    @classmethod
    def encapsulate_module(cls, module: nn.Module) -> List[str]:
        typename = type(module).__name__
        serializer = cls.module_to_serializer_cls.get(typename)
        if serializer is None:
            raise ValueError(
                f"Expected typename to be one of {list(cls.module_to_serializer_cls.keys())}, got {typename}"
            )
        assert issubclass(serializer, JsonSerializer)
        assert serializer._module_cls is not None
        if not isinstance(module, serializer._module_cls):
            raise ValueError(
                f"Expected module to be of type {serializer._module_cls.__name__}, "
                f"got {type(module)}"
            )
        metadata_dict = serializer.serialize_to_dict(module)
        raw_dict = {"typename": typename, "metadata_dict": metadata_dict}
        ir_metadata_tensor = torch.frombuffer(
            json.dumps(raw_dict).encode(), dtype=torch.uint8
        )
        module.register_buffer("ir_metadata", ir_metadata_tensor, persistent=False)
        serializer.swap_meta_forward(module)
        return serializer.children(module)

    @classmethod
    def decapsulate_module(
        cls, module: nn.Module, device: Optional[torch.device] = None
    ) -> nn.Module:
        raw_bytes = module.get_buffer("ir_metadata").numpy().tobytes()
        raw_dict = json.loads(raw_bytes.decode())
        typename = raw_dict["typename"]
        metadata_dict = raw_dict["metadata_dict"]
        if typename not in cls.module_to_serializer_cls:
            raise ValueError(
                f"Expected typename to be one of {list(cls.module_to_serializer_cls.keys())}, got {typename}"
            )
        serializer = cls.module_to_serializer_cls[typename]
        assert issubclass(serializer, JsonSerializer)
        module = serializer.deserialize_from_dict(metadata_dict, device, module)

        if serializer._module_cls is None:
            raise ValueError(
                "Must assign a nn.Module to class static variable _module_cls"
            )
        if not isinstance(module, serializer._module_cls):
            raise ValueError(
                f"Expected module to be of type {serializer._module_cls.__name__}, got {type(module)}"
            )
        return module


class EBCJsonSerializer(JsonSerializer):
    _module_cls = EmbeddingBagCollection

    @classmethod
    def swap_meta_forward(cls, module: nn.Module) -> None:
        assert isinstance(module, cls._module_cls)
        # pyre-ignore
        module.forward = ebc_meta_forward.__get__(module, cls._module_cls)

    @classmethod
    def serialize_to_dict(
        cls,
        module: nn.Module,
    ) -> Dict[str, Any]:
        ebc_metadata = EBCMetadata(
            tables=[
                embedding_bag_config_to_metadata(table_config)
                for table_config in module.embedding_bag_configs()
            ],
            is_weighted=module.is_weighted(),
            device=str(module.device),
        )
        ebc_metadata_dict = ebc_metadata.__dict__
        ebc_metadata_dict["tables"] = [
            table_config.__dict__ for table_config in ebc_metadata_dict["tables"]
        ]
        return ebc_metadata_dict

    @classmethod
    def deserialize_from_dict(
        cls,
        metadata_dict: Dict[str, Any],
        device: Optional[torch.device] = None,
        unflatten_ep: Optional[nn.Module] = None,
    ) -> nn.Module:
        tables = [
            EmbeddingBagConfigMetadata(**table_config)
            for table_config in metadata_dict["tables"]
        ]

        device = get_deserialized_device(metadata_dict.get("device"), device)
        return EmbeddingBagCollection(
            tables=[
                embedding_metadata_to_config(table_config) for table_config in tables
            ],
            is_weighted=metadata_dict["is_weighted"],
            device=device,
        )


JsonSerializer.module_to_serializer_cls["EmbeddingBagCollection"] = EBCJsonSerializer


class PWMJsonSerializer(JsonSerializer):
    _module_cls = PositionWeightedModule

    @classmethod
    def serialize_to_dict(cls, module: nn.Module) -> Dict[str, Any]:
        metadata = PositionWeightedModuleMetadata(
            max_feature_length=module.position_weight.shape[0],
        )
        return metadata.__dict__

    @classmethod
    def deserialize_from_dict(
        cls,
        metadata_dict: Dict[str, Any],
        device: Optional[torch.device] = None,
        unflatten_ep: Optional[nn.Module] = None,
    ) -> nn.Module:
        metadata = PositionWeightedModuleMetadata(**metadata_dict)
        return PositionWeightedModule(metadata.max_feature_length, device)


JsonSerializer.module_to_serializer_cls["PositionWeightedModule"] = PWMJsonSerializer


class PWMCJsonSerializer(JsonSerializer):
    _module_cls = PositionWeightedModuleCollection

    @classmethod
    def serialize_to_dict(cls, module: nn.Module) -> Dict[str, Any]:
        metadata = PositionWeightedModuleCollectionMetadata(
            max_feature_lengths=[  # convert to list of tuples to preserve the order
                (feature, len) for feature, len in module.max_feature_lengths.items()
            ],
        )
        return metadata.__dict__

    @classmethod
    def deserialize_from_dict(
        cls,
        metadata_dict: Dict[str, Any],
        device: Optional[torch.device] = None,
        unflatten_ep: Optional[nn.Module] = None,
    ) -> nn.Module:
        metadata = PositionWeightedModuleCollectionMetadata(**metadata_dict)
        max_feature_lengths = {
            feature: len for feature, len in metadata.max_feature_lengths
        }
        return PositionWeightedModuleCollection(max_feature_lengths, device)


JsonSerializer.module_to_serializer_cls["PositionWeightedModuleCollection"] = (
    PWMCJsonSerializer
)


class FPEBCJsonSerializer(JsonSerializer):
    _module_cls = FeatureProcessedEmbeddingBagCollection
    _children = ["_feature_processors", "_embedding_bag_collection"]

    @classmethod
    def serialize_to_dict(
        cls,
        module: nn.Module,
    ) -> Dict[str, Any]:
        if isinstance(module._feature_processors, FeatureProcessorsCollection):
            metadata = FPEBCMetadata(
                is_fp_collection=True,
                features=[],
            )
        else:
            metadata = FPEBCMetadata(
                is_fp_collection=False,
                features=list(module._feature_processors.keys()),
            )
        return metadata.__dict__

    @classmethod
    def deserialize_from_dict(
        cls,
        metadata_dict: Dict[str, Any],
        device: Optional[torch.device] = None,
        unflatten_ep: Optional[nn.Module] = None,
    ) -> nn.Module:
        metadata = FPEBCMetadata(**metadata_dict)
        assert unflatten_ep is not None
        if metadata.is_fp_collection:
            feature_processors = unflatten_ep._feature_processors
            assert isinstance(feature_processors, FeatureProcessorsCollection)
        else:
            feature_processors: dict[str, FeatureProcessor] = {}
            for feature in metadata.features:
                fp = getattr(unflatten_ep._feature_processors, feature)
                assert isinstance(fp, FeatureProcessor)
                feature_processors[feature] = fp
        ebc = unflatten_ep._embedding_bag_collection
        assert isinstance(ebc, EmbeddingBagCollection)
        return FeatureProcessedEmbeddingBagCollection(
            ebc,
            feature_processors,
        )


JsonSerializer.module_to_serializer_cls["FeatureProcessedEmbeddingBagCollection"] = (
    FPEBCJsonSerializer
)
