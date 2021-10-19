#!/usr/bin/env python3

import itertools
from typing import List, Optional, Callable

import torch
import torch.distributed as dist
from torch import nn
from torch.autograd.profiler import record_function
from torchrec.distributed.comm_ops import (
    alltoall_pooled,
    alltoall_sequence,
    reduce_scatter_pooled,
)
from torchrec.distributed.types import Awaitable, NoWait
from torchrec.sparse.jagged_tensor import KeyedJaggedTensor

try:
    torch.ops.load_library("//deeplearning/fbgemm/fbgemm_gpu:sparse_ops")
    torch.ops.load_library("//deeplearning/fbgemm/fbgemm_gpu:sparse_ops_cpu")
except OSError:
    pass


def _recat(local_split: int, num_splits: int, stagger: int = 1) -> List[int]:
    """
    Calculates relevant recat indices required to reorder All-to-All Collective

    Call Args:
        local_split: how many features in local split
        num_splits: how many splits (typically WORLD_SIZE)
        stagger: secondary reordering, (typically 1, but WORLD_SIZE/LOCAL_WORLD_SIZE for TWRW)

    Returns:
        List[int]

    Example:
    >>> _recat(2, 4, 1)
        [0, 2, 4, 6, 1, 3, 5, 7]
    >>> _recat(2, 4, 2)
        [0, 4, 2, 6, 1, 5, 3, 7]

    """
    recat: List[int] = []

    feature_order: List[int] = [
        x + num_splits // stagger * y
        for x in range(num_splits // stagger)
        for y in range(stagger)
    ]

    for i in range(local_split):
        for j in feature_order:  # range(num_splits):
            recat.append(i + j * local_split)
    return recat


def _split_lengths(
    splits: List[int], keys: List[str], offset_per_key: List[int]
) -> List[int]:
    # Calculates lengths [x1, x2, x3, ..., y1, y2], splits [3, ..., 2]
    #   -> [x1+x2+x3, ..., y1+y2]
    length_per_split: List[int] = []
    i = 0
    offset = 0
    for split in splits:
        new_offset = offset_per_key[i + split]
        length_per_split.append(new_offset - offset)
        i += split
        offset = new_offset
    return length_per_split


class KJTAllToAllAwaitable(Awaitable[KeyedJaggedTensor]):
    """
    Awaitable for KJT all2all

    Constructor Args:
        pg  (dist.ProcessGroup): ProcessGroup for AlltoAll communication.
        input (KeyedJaggedTensor): Input KJT tensor
        splits (List[int]): List of len(pg.size()) which indicates how many features to send to
            each pg.rank().  It is assumed the KeyedJaggedTensor is ordered by destination rank.
            Same for all ranks.
        keys (List[str]): KJT keys after all2all
        recat (torch.Tensor): recat tensor for reordering tensor order after all2all

    Call Args:
       None

    Returns:
        Synced KJT after all2all
    """

    def __init__(
        self,
        pg: dist.ProcessGroup,
        input: KeyedJaggedTensor,
        splits: List[int],
        keys: List[str],
        recat: torch.Tensor,
    ) -> None:
        super().__init__()
        self._workers: int = pg.size()
        self._input = input
        self._callback: Optional[
            Callable[[KeyedJaggedTensor], KeyedJaggedTensor]
        ] = None
        self._in_lengths_per_worker: List[int] = []
        self._out_lengths_per_worker: List[int] = []
        if self._workers == 1:
            return
        self._recat = recat
        self._splits = splits
        self._pg: dist.ProcessGroup = pg
        self._device: torch.device = input.values().device
        self._keys = keys

        dim_0 = splits[pg.rank()]
        dim_1 = input.stride()
        in_lengths = input.lengths().view(-1)
        out_lengths = torch.empty(
            dim_0 * dim_1 * self._workers,
            device=self._device,
            dtype=in_lengths.dtype,
        )

        with record_function("## all2all_data:lengths ##"):
            dist.all_to_all_single(
                output=out_lengths,
                input=in_lengths,
                output_split_sizes=[dim_0 * dim_1] * self._workers,
                input_split_sizes=[split * dim_1 for split in self._splits],
                group=self._pg,
                async_op=False,
            )

        self._in_lengths_per_worker = _split_lengths(
            splits, input.keys(), input.offset_per_key()
        )
        self._out_lengths_per_worker = (
            out_lengths.view(self._workers, -1).sum(dim=1).cpu().tolist()
        )
        in_values = input.values().view(-1)
        out_values = torch.empty(
            sum(self._out_lengths_per_worker),
            device=self._device,
            dtype=in_values.dtype,
        )
        # Pyre-fixme [11]
        self._values_awaitable: dist.Work = dist.all_to_all_single(
            output=out_values,
            input=in_values,
            output_split_sizes=self._out_lengths_per_worker,
            input_split_sizes=self._in_lengths_per_worker,
            group=self._pg,
            async_op=True,
        )

        self._values: torch.Tensor = out_values
        self._lengths: torch.Tensor = out_lengths

        self._weights_awaitable: Optional[dist.Work] = None
        self._weights: Optional[torch.Tensor] = None

        if input.weights_or_none() is not None:
            in_weights = input.weights().view(-1)
            out_weights = torch.empty(
                sum(self._out_lengths_per_worker),
                device=self._device,
                dtype=in_weights.dtype,
            )
            self._weights_awaitable: dist.Work = dist.all_to_all_single(
                output=out_weights,
                input=in_weights,
                output_split_sizes=self._out_lengths_per_worker,
                input_split_sizes=self._in_lengths_per_worker,
                group=self._pg,
                async_op=True,
            )
            self._weights: torch.Tensor = out_weights

    def wait(self) -> KeyedJaggedTensor:
        if self._workers == 1:
            # TODO: add callback logic to awaitable type directly
            self._input.sync()
            return (
                self._callback(self._input)
                if self._callback is not None
                else self._input
            )

        with record_function("## all2all_data:values ##"):
            self._values_awaitable.wait()

        if self._weights_awaitable:
            with record_function("## all2all_data:weights ##"):
                self._weights_awaitable.wait()

        keys = self._keys
        lengths = self._lengths
        values = self._values
        weights = self._weights

        with record_function("## all2all_data:recat_values ##"):
            if self._recat.numel():
                lengths, values, weights = torch.ops.fbgemm.permute_sparse_data(
                    self._recat,
                    lengths.view(self._workers * self._splits[self._pg.rank()], -1),
                    values,
                    weights,
                    values.numel(),
                )
                lengths = lengths.view(-1)

        ret = KeyedJaggedTensor.from_lengths_sync(
            keys=keys,
            values=values,
            weights=weights,
            lengths=lengths,
            stride=self._workers * self._input.stride(),
        )

        # TODO: add callback logic to awaitable type directly
        return self._callback(ret) if self._callback is not None else ret


class KJTAllToAll(nn.Module):
    """
    Redistributes KeyedJaggedTensor to a ProcessGroup according to splits

    Implementation utilizes alltoall collective as part of torch.distributed.
    Requires two collective calls, one to transmit final tensor lengths (to allocate
    correct space), and one to transmit actual sparse values.

    Example:

        >>> keys=['A','B','C']
        >>> splits=[2,1]
        >>> sdd = SparseDataDist(pg, splits, device)
        >>> awaitable = sdd(rank0_input)

        where:
            rank0_input is KeyedJaggedTensor holding

                    0           1           2
            'A'    [A.V0]       None        [A.V1, A.V2]
            'B'    None         [B.V0]      [B.V1]
            'C'    [C.V0]       [C.V1]      None

            rank1_input is KeyedJaggedTensor holding

                    0           1           2
            'A'     [A.V3]      [A.V4]      None
            'B'     None        [B.V2]     [B.V3, B.V4]
            'C'     [C.V2]      [C.V3]      None

        >>> rank0_output = awaitable.wait()

            rank0_output is KeyedJaggedTensor holding

                    0           1           2           3           4           5
            'A'     [A.V0]      None      [A.V1, A.V2]  [A.V3]      [A.V4]      None
            'B'     None        [B.V0]    [B.V1]        None        [B.V2]     [B.V3, B.V4]

            rank1_output is KeyedJaggedTensor holding
                    0           1           2           3           4           5
            'C'    [C.V0]       [C.V1]      None        [C.V2]      [C.V3]      None

    Constructor Args:
        pg  (dist.ProcessGroup): ProcessGroup for AlltoAll communication.
        splits (List[int]): List of len(pg.size()) which indicates how many features to send to
            each pg.rank().  It is assumed the KeyedJaggedTensor is ordered by destination rank.
            Same for all ranks.
        device (Optional[torch.device]): device on which buffers will be allocated
        stagger (int): stagger value to apply to recat tensor, see _recat function for more detail

    Call Args:
        input (KeyedJaggedTensor): Input KJT tensor

    Returns:
        None
    """

    def __init__(
        self,
        pg: dist.ProcessGroup,
        splits: List[int],
        device: Optional[torch.device] = None,
        stagger: int = 1,
    ) -> None:
        super().__init__()
        assert len(splits) == pg.size()
        self._pg: dist.ProcessGroup = pg
        self._splits = splits
        self._no_dist: bool = all(s == 0 for s in splits)
        self._splits_cumsum: List[int] = [0] + list(itertools.accumulate(splits))
        self.register_buffer(
            "_recat",
            torch.tensor(
                _recat(
                    local_split=splits[pg.rank()],
                    num_splits=len(splits),
                    stagger=stagger,
                ),
                device=device,
                dtype=torch.int,
            ),
        )

    def forward(self, input: KeyedJaggedTensor) -> Awaitable[KeyedJaggedTensor]:
        """
        Sends input to relevant ProcessGroup ranks

        Call Args:
            input (KeyedJaggedTensor): A Jagged tensor of values to distribute

        Returns:
            awaitable of a KeyedJaggedTensor
        """
        with torch.no_grad():
            if self._no_dist:
                assert len(input.keys()) == 0
                return NoWait(input)
            else:
                rank = dist.get_rank(self._pg)
                local_keys = input.keys()[
                    self._splits_cumsum[rank] : self._splits_cumsum[rank + 1]
                ]

                return KJTAllToAllAwaitable(
                    pg=self._pg,
                    input=input,
                    splits=self._splits,
                    keys=local_keys,
                    recat=self._recat,
                )


class PooledEmbeddingsAwaitable(Awaitable[torch.Tensor]):
    def __init__(
        self,
        tensor_awaitable: Awaitable[torch.Tensor],
    ) -> None:
        super().__init__()
        self._tensor_awaitable = tensor_awaitable
        self._callback: Optional[Callable[[torch.Tensor], torch.Tensor]] = None

    def wait(self) -> torch.Tensor:
        ret = self._tensor_awaitable.wait()
        # TODO: add callback logic to awaitable type directly
        if self._callback is not None:
            ret = self._callback(ret)

        return ret


class PooledEmbeddingsAllToAll(nn.Module):
    # TODO: potentially refactor to take KT instead of torch.Tensor: D29174501
    """
    Shards batchs and collects keys of Tensor with a ProcessGroup according to dim_sum_per_rank

    Implementation utilizes alltoall_pooled operation.

    Example:
        >>> dim_sum_per_rank = [2, 1]
        >>> a2a = PooledEmbeddingsAllToAll(pg, dim_sum_per_rank, device)

        >>> t0 = torch.rand((6, 2))
        >>> t1 = torch.rand((6, 1))
        >>> rank0_output = a2a(t0).wait()
        >>> rank1_output = a2a(t1).wait()
        >>> print(rank0_output.size())
            torch.Size([3, 3])
        >>> print(rank1_output.size())
            torch.Size([3, 3])

    Constructor Args:
        pg: dist.ProcessGroup,
        dim_sum_per_rank: List[int],
        device: Optional[torch.device] = None,

    Call Args:
        local_embs: torch.Tensor

    Returns:
        PooledEmbeddingsAwaitable
    """

    def __init__(
        self,
        pg: dist.ProcessGroup,
        dim_sum_per_rank: List[int],
        device: Optional[torch.device] = None,
    ) -> None:
        super().__init__()
        self._pg = pg

        self._dim_sum_per_rank = dim_sum_per_rank
        self.register_buffer(
            "_dim_sum_per_rank_tensor",
            torch.tensor(dim_sum_per_rank, device=device, dtype=torch.int),
        )
        cumsum_dim_sum_per_rank = list(itertools.accumulate(dim_sum_per_rank))
        self.register_buffer(
            "_cumsum_dim_sum_per_rank_tensor",
            torch.tensor(cumsum_dim_sum_per_rank, device=device, dtype=torch.int),
        )

    def forward(self, local_embs: torch.Tensor) -> PooledEmbeddingsAwaitable:
        if local_embs.numel() == 0:
            local_embs.view(local_embs.size(0) * self._pg.size(), 0)
        tensor_awaitable = alltoall_pooled(
            a2a_pooled_embs_tensor=local_embs,
            dim_sum_per_rank=self._dim_sum_per_rank,
            mixed_dim=True,
            dim_sum_per_rank_tensor=self._dim_sum_per_rank_tensor,
            cumsum_dim_sum_per_rank_tensor=self._cumsum_dim_sum_per_rank_tensor,
            group=self._pg,
        )
        return PooledEmbeddingsAwaitable(
            tensor_awaitable=tensor_awaitable,
        )


class PooledEmbeddingsReduceScatter(nn.Module):
    def __init__(
        self,
        pg: dist.ProcessGroup,
    ) -> None:
        """The module class that wraps reduce-scatter communication primitive
        for pooled embedding communication in row-wise and twrw sharding.

        For pooled embeddings, we have a local model-parallel output tensor with
        a layout of [num_buckets x batch_size, dimension]. We need to sum over num_buckets dimension across batches.
        We split tensor along the first dimension into equal chunks(tensor slices of different buckets) and
        reduce them into the output tensor and scatter the results for corresponding ranks.
        The class returns the async Awaitable handle for pooled embeddings tensor.
        The reduce-scatter is only available for nccl backend.

        Constructor Args::
            pg (dist.ProcessGroup): The process group that the reduce-scatter communication happens within.

        Call Args:
            input (torch.Tensor): tensor of shape [num_buckets x batch_size, dimension].

        Returns:
            output (torch.Tensor): PooledEmbeddingsAwaitable of tensor of shape [batch_size, dimension].

        Example:
            >>> init_distributed(rank=rank, size=2, backend="nccl")
            >>> pg = dist.new_group(backend="nccl")
            >>> input = torch.randn(2 * 2, 2)
            >>> m = PooledEmbeddingsReduceScatter(pg)
            >>> output = m(input)
            >>> tensor = output.wait()
        """
        super().__init__()
        self._pg = pg

    def forward(self, local_embs: torch.Tensor) -> PooledEmbeddingsAwaitable:
        tensor_awaitable = reduce_scatter_pooled(
            list(torch.chunk(local_embs, self._pg.size(), dim=0)), self._pg
        )
        return PooledEmbeddingsAwaitable(tensor_awaitable=tensor_awaitable)


class SequenceEmbeddingsAwaitable(Awaitable[torch.Tensor]):
    def __init__(
        self,
        tensor_awaitable: Awaitable[torch.Tensor],
        unbucketize_permute_tensor: Optional[torch.Tensor],
        embedding_dim: int,
    ) -> None:
        super().__init__()
        self._tensor_awaitable = tensor_awaitable
        self._unbucketize_permute_tensor = unbucketize_permute_tensor
        self._callback: Optional[Callable[[torch.Tensor], torch.Tensor]] = None
        self._embedding_dim = embedding_dim

    def wait(self) -> torch.Tensor:
        ret = self._tensor_awaitable.wait()
        # TODO: add callback logic to awaitable type directly
        if self._callback is not None:
            ret = self._callback(ret)
        if self._unbucketize_permute_tensor is not None:
            ret = torch.index_select(
                ret.view(-1, self._embedding_dim),
                0,
                self._unbucketize_permute_tensor,
            )
        return ret


class SequenceEmbeddingAllToAll(nn.Module):
    def __init__(
        self,
        pg: dist.ProcessGroup,
        features_per_rank: List[int],
        device: Optional[torch.device] = None,
    ) -> None:
        super().__init__()
        self._pg = pg

        forward_recat = []
        for j in range(self._pg.size()):
            for i in range(features_per_rank[self._pg.rank()]):
                forward_recat.append(j + i * self._pg.size())
        self.register_buffer(
            "_forward_recat_tensor",
            torch.tensor(forward_recat, device=device, dtype=torch.int),
        )
        backward_recat = []
        for i in range(features_per_rank[self._pg.rank()]):
            for j in range(self._pg.size()):
                backward_recat.append(i + j * features_per_rank[self._pg.rank()])
        self.register_buffer(
            "_backward_recat_tensor",
            torch.tensor(backward_recat, device=device, dtype=torch.int),
        )

    def forward(
        self,
        local_embs: torch.Tensor,
        lengths: torch.Tensor,
        input_splits: List[int],
        output_splits: List[int],
        unbucketize_permute_tensor: Optional[torch.Tensor] = None,
    ) -> SequenceEmbeddingsAwaitable:
        tensor_awaitable = alltoall_sequence(
            a2a_sequence_embs_tensor=local_embs,
            forward_recat_tensor=self._forward_recat_tensor,
            backward_recat_tensor=self._backward_recat_tensor,
            lengths_after_sparse_data_all2all=lengths,
            input_splits=input_splits,
            output_splits=output_splits,
            group=self._pg,
        )
        return SequenceEmbeddingsAwaitable(
            tensor_awaitable=tensor_awaitable,
            unbucketize_permute_tensor=unbucketize_permute_tensor,
            embedding_dim=local_embs.shape[1],
        )
