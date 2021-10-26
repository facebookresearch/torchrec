#!/usr/bin/env python3

from enum import Enum
from typing import Dict, Tuple

from torchrec.distributed.embedding_types import EmbeddingComputeKernel

HBM_CAP_DEFAULT: int = 32 * 1024 * 1024 * 1024  # 32 GB
DDR_CAP_DEFAULT: int = 2 * 1024 * 1024 * 1024 * 1024  # 2 TB

INTRA_NODE_BANDWIDTH: int = 600
CROSS_NODE_BANDWIDTH: int = 12

DEFAULT_CW_DIM: int = 32
DEFAULT_POOLING_FACTOR: float = 1.0

BIGINT_DTYPE: float = 8.0


class PartitionByType(Enum):
    """
    Well-known partition types
    """

    # Partitioning based on device
    DEVICE = "device"
    # Partitioning based on host
    HOST = "host"
    # Uniform, (ie. fixed layout)
    UNIFORM = "uniform"


DDR_MEM_BW: int = 51
HBM_MEM_BW: int = 897
CACHING_FACTOR: float = 0.2


KERNEL_LOOKUP_BW: Dict[Tuple[str, str], float] = {
    # CPU
    ("cpu", EmbeddingComputeKernel.DENSE.value): 1 * DDR_MEM_BW,
    ("cpu", EmbeddingComputeKernel.SPARSE.value): 1.1 * DDR_MEM_BW,
    ("cpu", EmbeddingComputeKernel.BATCHED_DENSE.value): 1.2 * DDR_MEM_BW,
    ("cpu", EmbeddingComputeKernel.BATCHED_FUSED.value): 1.3 * DDR_MEM_BW,
    # CUDA
    ("cuda", EmbeddingComputeKernel.DENSE.value): 1.1 * DDR_MEM_BW,
    ("cuda", EmbeddingComputeKernel.SPARSE.value): 1.2 * DDR_MEM_BW,
    ("cuda", EmbeddingComputeKernel.BATCHED_DENSE.value): 1.3 * DDR_MEM_BW,
    ("cuda", EmbeddingComputeKernel.BATCHED_FUSED.value): 1.5 * HBM_MEM_BW,
    ("cuda", EmbeddingComputeKernel.BATCHED_FUSED_UVM.value): 1.5 * DDR_MEM_BW,
    ("cuda", EmbeddingComputeKernel.BATCHED_FUSED_UVM_CACHING.value): 1.5
    * (CACHING_FACTOR * HBM_MEM_BW + (1 - CACHING_FACTOR) * DDR_MEM_BW),
}
