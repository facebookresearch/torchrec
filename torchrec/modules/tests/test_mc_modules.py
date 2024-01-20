#!/usr/bin/env python3
# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
#
# This source code is licensed under the BSD-style license found in the
# LICENSE file in the root directory of this source tree.

import unittest
from typing import Dict

import torch
from torchrec.modules.mc_modules import (
    DistanceLFU_EvictionPolicy,
    LFU_EvictionPolicy,
    LRU_EvictionPolicy,
    MCHManagedCollisionModule,
)
from torchrec.sparse.jagged_tensor import JaggedTensor


class TestEvictionPolicy(unittest.TestCase):
    def test_lfu_eviction(self) -> None:
        mc_module = MCHManagedCollisionModule(
            zch_size=5,
            device=torch.device("cpu"),
            eviction_policy=LFU_EvictionPolicy(),
            eviction_interval=1,
            input_hash_size=100,
        )

        # check initial state
        _mch_sorted_raw_ids = mc_module._mch_sorted_raw_ids
        self.assertEqual(list(_mch_sorted_raw_ids), [torch.iinfo(torch.int64).max] * 5)
        _mch_counts = mc_module._mch_counts
        self.assertEqual(list(_mch_counts), [0] * 5)

        # insert some values to zch
        # we have 10 counts of 4 and 1 count of 5
        mc_module._mch_sorted_raw_ids[0:2] = torch.tensor([4, 5])
        mc_module._mch_counts[0:2] = torch.tensor([10, 1])

        ids = [3, 4, 5, 6, 6, 6, 7, 7, 7, 8, 8, 8, 9, 10]
        features: Dict[str, JaggedTensor] = {
            "f1": JaggedTensor(
                values=torch.tensor(ids, dtype=torch.int64),
                lengths=torch.tensor([1] * len(ids), dtype=torch.int64),
            )
        }
        mc_module.profile(features)

        # 5, empty, empty, empty will be evicted
        # 6, 7, 8 will be added
        _mch_sorted_raw_ids = mc_module._mch_sorted_raw_ids
        self.assertEqual(
            list(_mch_sorted_raw_ids), [4, 6, 7, 8, torch.iinfo(torch.int64).max]
        )
        # 11 counts of 5, 3 counts of 6, 3 counts of 7, 3 counts of 8
        _mch_counts = mc_module._mch_counts
        self.assertEqual(list(_mch_counts), [11, 3, 3, 3, torch.iinfo(torch.int64).max])

    def test_lru_eviction(self) -> None:
        mc_module = MCHManagedCollisionModule(
            zch_size=5,
            device=torch.device("cpu"),
            eviction_policy=LRU_EvictionPolicy(decay_exponent=1.0),
            eviction_interval=1,
            input_hash_size=100,
        )

        # check initial state
        _mch_sorted_raw_ids = mc_module._mch_sorted_raw_ids
        self.assertEqual(list(_mch_sorted_raw_ids), [torch.iinfo(torch.int64).max] * 5)
        _mch_last_access_iter = mc_module._mch_last_access_iter
        self.assertEqual(list(_mch_last_access_iter), [0] * 5)

        ids = [5, 6, 7]
        features: Dict[str, JaggedTensor] = {
            "f1": JaggedTensor(
                values=torch.tensor(ids, dtype=torch.int64),
                lengths=torch.tensor([1] * len(ids), dtype=torch.int64),
            )
        }
        mc_module.profile(features)

        ids = [3, 4, 5]
        features: Dict[str, JaggedTensor] = {
            "f1": JaggedTensor(
                values=torch.tensor(ids, dtype=torch.int64),
                lengths=torch.tensor([1] * len(ids), dtype=torch.int64),
            )
        }
        mc_module.profile(features)

        ids = [7, 8]
        features: Dict[str, JaggedTensor] = {
            "f1": JaggedTensor(
                values=torch.tensor(ids, dtype=torch.int64),
                lengths=torch.tensor([1] * len(ids), dtype=torch.int64),
            )
        }
        mc_module.profile(features)

        _mch_sorted_raw_ids = mc_module._mch_sorted_raw_ids
        self.assertEqual(
            list(_mch_sorted_raw_ids),
            [3, 4, 7, 8, torch.iinfo(torch.int64).max],
        )
        _mch_last_access_iter = mc_module._mch_last_access_iter
        self.assertEqual(list(_mch_last_access_iter), [2, 2, 3, 3, 3])

    def test_distance_lfu_eviction(self) -> None:
        mc_module = MCHManagedCollisionModule(
            zch_size=5,
            device=torch.device("cpu"),
            eviction_policy=DistanceLFU_EvictionPolicy(decay_exponent=1.0),
            eviction_interval=1,
            input_hash_size=100,
        )

        # check initial state
        _mch_sorted_raw_ids = mc_module._mch_sorted_raw_ids
        self.assertEqual(list(_mch_sorted_raw_ids), [torch.iinfo(torch.int64).max] * 5)
        _mch_counts = mc_module._mch_counts
        self.assertEqual(list(_mch_counts), [0] * 5)
        _mch_last_access_iter = mc_module._mch_last_access_iter
        self.assertEqual(list(_mch_last_access_iter), [0] * 5)

        ids = [5, 5, 5, 5, 5, 6]
        features: Dict[str, JaggedTensor] = {
            "f1": JaggedTensor(
                values=torch.tensor(ids, dtype=torch.int64),
                lengths=torch.tensor([1] * len(ids), dtype=torch.int64),
            )
        }
        mc_module.profile(features)

        ids = [3, 4]
        features: Dict[str, JaggedTensor] = {
            "f1": JaggedTensor(
                values=torch.tensor(ids, dtype=torch.int64),
                lengths=torch.tensor([1] * len(ids), dtype=torch.int64),
            )
        }
        mc_module.profile(features)

        ids = [7, 8]
        features: Dict[str, JaggedTensor] = {
            "f1": JaggedTensor(
                values=torch.tensor(ids, dtype=torch.int64),
                lengths=torch.tensor([1] * len(ids), dtype=torch.int64),
            )
        }
        mc_module.profile(features)

        _mch_sorted_raw_ids = mc_module._mch_sorted_raw_ids
        self.assertEqual(
            list(_mch_sorted_raw_ids),
            [3, 5, 7, 8, torch.iinfo(torch.int64).max],
        )
        _mch_counts = mc_module._mch_counts
        self.assertEqual(list(_mch_counts), [1, 5, 1, 1, torch.iinfo(torch.int64).max])
        _mch_last_access_iter = mc_module._mch_last_access_iter
        self.assertEqual(list(_mch_last_access_iter), [2, 1, 3, 3, 3])

    def test_distance_lfu_eviction_fast_decay(self) -> None:
        mc_module = MCHManagedCollisionModule(
            zch_size=5,
            device=torch.device("cpu"),
            eviction_policy=DistanceLFU_EvictionPolicy(decay_exponent=10.0),
            eviction_interval=1,
            input_hash_size=100,
        )

        # check initial state
        _mch_sorted_raw_ids = mc_module._mch_sorted_raw_ids
        self.assertEqual(list(_mch_sorted_raw_ids), [torch.iinfo(torch.int64).max] * 5)
        _mch_counts = mc_module._mch_counts
        self.assertEqual(list(_mch_counts), [0] * 5)
        _mch_last_access_iter = mc_module._mch_last_access_iter
        self.assertEqual(list(_mch_last_access_iter), [0] * 5)

        ids = [5, 5, 5, 5, 5, 6]
        features: Dict[str, JaggedTensor] = {
            "f1": JaggedTensor(
                values=torch.tensor(ids, dtype=torch.int64),
                lengths=torch.tensor([1] * len(ids), dtype=torch.int64),
            )
        }
        mc_module.profile(features)

        ids = [3, 4]
        features: Dict[str, JaggedTensor] = {
            "f1": JaggedTensor(
                values=torch.tensor(ids, dtype=torch.int64),
                lengths=torch.tensor([1] * len(ids), dtype=torch.int64),
            )
        }
        mc_module.profile(features)

        ids = [7, 8]
        features: Dict[str, JaggedTensor] = {
            "f1": JaggedTensor(
                values=torch.tensor(ids, dtype=torch.int64),
                lengths=torch.tensor([1] * len(ids), dtype=torch.int64),
            )
        }
        mc_module.profile(features)

        _mch_sorted_raw_ids = mc_module._mch_sorted_raw_ids
        self.assertEqual(
            list(_mch_sorted_raw_ids),
            [3, 4, 7, 8, torch.iinfo(torch.int64).max],
        )
        _mch_counts = mc_module._mch_counts
        self.assertEqual(list(_mch_counts), [1, 1, 1, 1, torch.iinfo(torch.int64).max])
        _mch_last_access_iter = mc_module._mch_last_access_iter
        self.assertEqual(list(_mch_last_access_iter), [2, 2, 3, 3, 3])
