#!/usr/bin/env python3
# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
#
# This source code is licensed under the BSD-style license found in the
# LICENSE file in the root directory of this source tree.

from typing import List, Tuple

import torch
from torch.distributed.checkpoint.metadata import (
    ChunkStorageMetadata,
    MetadataIndex,
    TensorProperties,
    TensorStorageMetadata,
)
from torch.distributed.checkpoint.planner import (
    TensorWriteData,
    WriteItem,
    WriteItemType,
)

aten = torch.ops.aten  # pyre-ignore[5]: Globally accessible variable `aten` has no type specified.


class LocalShardsWrapper(torch.Tensor):  # pyre-ignore[13]: pyre is bad at __new__
    __slots__ = ["_local_shards", "_storage_meta"]
    _local_shards: List[torch.Tensor]
    _storage_meta: TensorStorageMetadata

    @staticmethod
    def __new__(
        cls, local_shards: List[torch.Tensor], local_offsets: List[Tuple[int, ...]]
    ) -> "LocalShardsWrapper":
        assert len(local_shards) > 0
        assert len(local_shards) == len(local_offsets)
        assert all(
            tensor.device == local_shards[0].device for tensor in local_shards[1:]
        )

        # we calculate the total tensor size by "concat" on second tensor dimension
        cat_tensor_shape = list(local_shards[0].size())
        if len(local_shards) > 1:  # column-wise sharding
            for shard in local_shards[1:]:
                cat_tensor_shape[1] += shard.size()[1]

        wrapper_properties = TensorProperties.create_from_tensor(local_shards[0])
        wrapper_shape = torch.Size(cat_tensor_shape)
        chunks_meta = [
            ChunkStorageMetadata(
                offsets=torch.Size(offset),
                sizes=shard.size(),
            )
            for shard, offset in zip(local_shards, local_offsets)
        ]

        r = torch.Tensor._make_wrapper_subclass(  # type: ignore[attr-defined]
            cls,
            torch.Size(cat_tensor_shape),
        )
        r._local_shards = local_shards
        r._storage_meta = TensorStorageMetadata(
            properties=wrapper_properties,
            size=wrapper_shape,
            chunks=chunks_meta,
        )

        return r

    # necessary for ops dispatching from this subclass to its local shards
    @classmethod
    # pyre-fixme[3]: Return type must be annotated.
    # pyre-fixme[2]: Parameter must be annotated.
    def __torch_dispatch__(cls, func, types, args=(), kwargs=None):
        kwargs = kwargs or {}

        dispatcher = {
            torch.ops._c10d_functional.all_gather_into_tensor.default: cls.handle_all_gather_into_tensor,
            torch.ops._c10d_functional.wait_tensor.default: cls.handle_wait_tensor,
            aten._to_copy.default: cls.handle_to_copy,
            aten.view.default: cls.handle_view,
            aten.equal.default: cls.handle_equal,
            aten.detach.default: cls.handle_detach,
            aten.clone.default: cls.handle_clone,
        }

        if func in dispatcher:
            return dispatcher[func](args, kwargs)
        else:
            raise NotImplementedError(
                f"{func} is not supported for LocalShardsWrapper!"
            )

    @staticmethod
    # pyre-fixme[3]: Return type must be annotated.
    # pyre-fixme[2]: Parameter must be annotated.
    def handle_all_gather_into_tensor(args, kwargs):
        dim = args[0].local_sizes()[0][1]
        cat_tensor = torch.cat(
            [t.view(-1) for t in args[0].local_shards()], dim=0
        ).view(-1, dim)
        return torch.ops._c10d_functional.all_gather_into_tensor.default(
            cat_tensor, *args[1:], **kwargs
        )

    @staticmethod
    # pyre-fixme[3]: Return type must be annotated.
    # pyre-fixme[2]: Parameter must be annotated.
    def handle_wait_tensor(args, kwargs):
        return torch.ops._c10d_functional.wait_tensor(args[0])

    @staticmethod
    # pyre-fixme[3]: Return type must be annotated.
    # pyre-fixme[2]: Parameter must be annotated.
    def handle_to_copy(args, kwargs):
        res_shards_list = [
            aten._to_copy.default(shard, *args[1:], **kwargs)
            for shard in args[0].local_shards()
        ]
        return LocalShardsWrapper(res_shards_list, args[0].local_offsets())

    @staticmethod
    # pyre-fixme[3]: Return type must be annotated.
    # pyre-fixme[2]: Parameter must be annotated.
    def handle_view(args, kwargs):
        # TODO, do we need to change the shape of associated offsets?
        res_shards_list = [
            aten.view.default(shard, args[1], **kwargs)
            for shard in args[0].local_shards()
        ]
        return LocalShardsWrapper(res_shards_list, args[0].local_offsets())

    @staticmethod
    # pyre-fixme[3]: Return type must be annotated.
    # pyre-fixme[2]: Parameter must be annotated.
    def handle_equal(args, kwargs):
        """
        LocalShardsWrapper equal impl also checks for equality of storage metadata
        and the order of shards
        """
        a, b = args[0], args[1]
        if len(a.local_shards()) != len(b.local_shards()):
            return False
        if not all(
            aten.equal.default(x, y) for x, y in zip(a.local_shards(), b.local_shards())
        ):
            return False
        if not a.storage_metadata() == b.storage_metadata():
            return False
        return True

    @staticmethod
    # pyre-fixme[3]: Return type must be annotated.
    # pyre-fixme[2]: Parameter must be annotated.
    def handle_detach(args, kwargs):
        self_ls = args[0]
        deatched_local_shards = [
            aten.detach.default(shard) for shard in self_ls.local_shards()
        ]
        self_ls._local_shards = deatched_local_shards
        self_ls._storage_meta.properties.requires_grad = False
        return self_ls

    @staticmethod
    # pyre-fixme[3]: Return type must be annotated.
    # pyre-fixme[2]: Parameter must be annotated.
    def handle_clone(args, kwargs):
        self_ls = args[0]
        desired_memory_format = kwargs.get("memory_format", None)
        if desired_memory_format and desired_memory_format != torch.preserve_format:
            raise NotImplementedError(
                f"{desired_memory_format} is not supported for LocalShardsWrapper!"
            )
        cloned_local_shards = [
            shard.clone(memory_format=desired_memory_format)
            for shard in self_ls._local_shards
        ]
        return LocalShardsWrapper(cloned_local_shards, self_ls.local_offsets())

    @property
    def device(self) -> torch._C.device:
        return self._local_shards[0].device

    @property
    def is_meta(self) -> bool:
        return self._local_shards[0].is_meta

    # pyre-ignore[14]
    def is_pinned(self) -> bool:
        return self._storage_meta.properties.pin_memory

    # pyre-ignore[14]
    def requires_grad_(self, requires_grad: bool = True) -> "LocalShardsWrapper":
        self._storage_meta.properties.requires_grad = requires_grad
        [shard.requires_grad_(requires_grad) for shard in self._local_shards]
        return self

    def local_shards(self) -> List[torch.Tensor]:
        """
        Returns a list of :class:`torch.Tensor' corresponding to the
        local shards for this rank. Returns an empty list if the current rank
        does not host any shards for this Tensor.
        """
        return self._local_shards

    def local_sizes(self) -> List[torch.Size]:
        """
        Returns a list of :class:`torch.Size' corresponding to the
        local sizes for the shards on this rank. Returns an empty list if the current rank
        does not host any shards for this Tensor.
        """
        return [chunk.sizes for chunk in self._storage_meta.chunks]

    def local_offsets(self) -> List[torch.Size]:
        """
        Returns a list of :class:`torch.Size' corresponding to the
        local offsets for the shards on this rank. Returns an empty list if the current rank
        does not host any shards for this Tensor.
        """
        return [chunk.offsets for chunk in self._storage_meta.chunks]

    @property
    def local_chunks(self) -> List[ChunkStorageMetadata]:
        """
        Returns a :class:`List[ChunkStorageMetadata]` object corresponding to the
        metadata for each tensor shard
        """
        return self._storage_meta.chunks

    def local_shards_sizes_offsets(
        self,
    ) -> List[Tuple[torch.Tensor, torch.Size, torch.Size]]:
        """
        Returns a :class:`List[Tuple[torch.Tensor, torch.Size, torch.Size]]` object corresponding to the
        metadata for each tensor shard
        """
        return [
            (tensor, chunk.sizes, chunk.offsets)
            for tensor, chunk in zip(self._local_shards, self._storage_meta.chunks)
        ]

    def storage_metadata(self) -> TensorStorageMetadata:
        """
        Returns a :class:`TensorStorageMetadata` object corresponding to the
        metadata for the local tensor on current rank
        """
        return self._storage_meta

    def _create_write_items(self, fqn, size) -> List[WriteItem]:
        """
        For compatibility with DCP, we support creation of WriteItems
        such that they can be saved properly.
        """
        return [
            WriteItem(
                index=MetadataIndex(fqn, chunks.offsets),
                type=WriteItemType.SHARD,
                tensor_data=TensorWriteData(
                    chunk=ChunkStorageMetadata(
                        offsets=chunks.offsets,
                        sizes=chunks.sizes,
                    ),
                    properties=self._storage_meta.properties,
                    size=size,
                ),
            )
            for tensor, chunks in zip(self.local_shards(), self.local_chunks)
        ]

    def __hash__(self):
        return id(self)

    # pyre-fixme[14]: `__repr__` overrides method defined in `torch._tensor.Tensor` inconsistently.
    # pyre-fixme[3]: Return type must be annotated.
    def __repr__(self):
        return f"LocalShardsWrapper:{self._local_shards} {self._storage_meta}"

    def __str__(self) -> str:
        return f"LocalShardsWrapper:{self._local_shards} {self._storage_meta}"
