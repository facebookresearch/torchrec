#!/usr/bin/env python3
# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
#
# This source code is licensed under the BSD-style license found in the
# LICENSE file in the root directory of this source tree.


import random
import unittest
from typing import List, Tuple

from torchrec.distributed.embedding_dim_bucketer import (
    EmbDimBucketer,
    EmbDimBucketerPolicy,
    should_do_dim_bucketing,
)

from torchrec.distributed.embedding_types import (
    EmbeddingComputeKernel,
    ShardedEmbeddingTable,
)
from torchrec.modules.embedding_configs import DataType


class TestEmbDimBucketer(unittest.TestCase):
    def setUp(self) -> None:
        super().setUp()

    def gen_tables(self) -> Tuple[List[ShardedEmbeddingTable], int]:
        num_tables = 103
        num_buckets = 11
        embeddings: List[ShardedEmbeddingTable] = []
        buckets = random.sample(range(1024), num_buckets)

        for i in range(num_tables):
            embeddings.append(
                ShardedEmbeddingTable(
                    name=f"table_{i}",
                    embedding_dim=buckets[i % num_buckets],
                    num_embeddings=random.randint(100, 500000),
                    data_type=DataType.FP16,
                    compute_kernel=EmbeddingComputeKernel.FUSED_UVM_CACHING,
                )
            )
        return embeddings, len(buckets)

    def gen_single_dim_tables(self) -> List[ShardedEmbeddingTable]:
        num_tables = 47
        embeddings: List[ShardedEmbeddingTable] = []
        for i in range(num_tables):
            embeddings.append(
                ShardedEmbeddingTable(
                    name=f"table_{i}",
                    embedding_dim=16,
                    num_embeddings=random.randint(100, 500000),
                    data_type=DataType.FP16,
                )
            )
        return embeddings

    def test_single_bucket_tables(self) -> None:
        embedding_tables = self.gen_single_dim_tables()
        emb_dim_bucketer = EmbDimBucketer(
            embedding_tables, EmbDimBucketerPolicy.CACHELINE_BUCKETS
        )
        self.assertTrue(emb_dim_bucketer.bucket_count() == 1)

    def test_single_bucket_policy(self) -> None:
        embedding_tables, _ = self.gen_tables()
        emb_dim_bucketer = EmbDimBucketer(
            embedding_tables, EmbDimBucketerPolicy.SINGLE_BUCKET
        )
        self.assertTrue(emb_dim_bucketer.bucket_count() == 1)

    def test_cacheline_bucket_policy(self) -> None:
        embedding_tables, _ = self.gen_tables()
        emb_dim_bucketer = EmbDimBucketer(
            embedding_tables, EmbDimBucketerPolicy.CACHELINE_BUCKETS
        )
        for i in range(emb_dim_bucketer.bucket_count()):
            self.assertTrue(i in emb_dim_bucketer.emb_dim_buckets.values())

    def test_all_bucket_policy(self) -> None:
        embedding_tables, num_buckets = self.gen_tables()
        emb_dim_bucketer = EmbDimBucketer(
            embedding_tables, EmbDimBucketerPolicy.ALL_BUCKETS
        )

        self.assertTrue(emb_dim_bucketer.bucket_count() == num_buckets)

        for i in range(emb_dim_bucketer.bucket_count()):
            self.assertTrue(i in emb_dim_bucketer.emb_dim_buckets.values())

    def test_should_do_dim_bucketing(self) -> None:
        embedding_tables, _ = self.gen_tables()
        self.assertFalse(should_do_dim_bucketing(embedding_tables))
