#!/usr/bin/env python3
# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
#
# This source code is licensed under the BSD-style license found in the
# LICENSE file in the root directory of this source tree.

# pyre-strict

import copy
import unittest
from dataclasses import dataclass
from functools import partial
from typing import cast, List, Optional, Tuple, Type
from unittest.mock import MagicMock

import torch
from hypothesis import given, settings, strategies as st, Verbosity
from torch import nn, optim
from torchrec.distributed import DistributedModelParallel
from torchrec.distributed.embedding_types import EmbeddingComputeKernel
from torchrec.distributed.embeddingbag import EmbeddingBagCollectionSharder
from torchrec.distributed.fp_embeddingbag import (
    FeatureProcessedEmbeddingBagCollectionSharder,
    ShardedFeatureProcessedEmbeddingBagCollection,
)
from torchrec.distributed.sharding_plan import (
    construct_module_sharding_plan,
    table_wise,
)
from torchrec.distributed.test_utils.test_model import (
    ModelInput,
    TestEBCSharder,
    TestSparseNN,
)
from torchrec.distributed.test_utils.test_sharding import copy_state_dict
from torchrec.distributed.tests.test_fp_embeddingbag_utils import (
    create_module_and_freeze,
)
from torchrec.distributed.train_pipeline.tests.test_train_pipelines_base import (
    TrainPipelineSparseDistTestBase,
)
from torchrec.distributed.train_pipeline.train_pipelines import (
    EvalPipelineSparseDist,
    PrefetchTrainPipelineSparseDist,
    StagedTrainPipeline,
    TrainPipelineBase,
    TrainPipelineSemiSync,
    TrainPipelineSparseDist,
)
from torchrec.distributed.train_pipeline.utils import (
    DataLoadingThread,
    get_h2d_func,
    PipelinedForward,
    PipelineStage,
    SparseDataDistUtil,
    StageOut,
    TrainPipelineContext,
)
from torchrec.distributed.types import (
    ModuleSharder,
    ShardingEnv,
    ShardingPlan,
    ShardingType,
)
from torchrec.modules.embedding_configs import DataType

from torchrec.optim.keyed import KeyedOptimizerWrapper
from torchrec.optim.optimizers import in_backward_optimizer_filter
from torchrec.streamable import Pipelineable


@dataclass
class ModelInputSimple(Pipelineable):
    float_features: torch.Tensor
    label: torch.Tensor

    def to(self, device: torch.device, non_blocking: bool) -> "ModelInputSimple":
        return ModelInputSimple(
            float_features=self.float_features.to(
                device=device, non_blocking=non_blocking
            ),
            label=self.label.to(device=device, non_blocking=non_blocking),
        )

    def record_stream(self, stream: torch.cuda.streams.Stream) -> None:
        self.float_features.record_stream(stream)
        self.label.record_stream(stream)


class TestModule(nn.Module):
    def __init__(self) -> None:
        super().__init__()
        self.model = nn.Linear(10, 1)
        self.loss_fn = nn.BCEWithLogitsLoss()

    def forward(
        self, model_input: ModelInputSimple
    ) -> Tuple[torch.Tensor, torch.Tensor]:
        pred = self.model(model_input.float_features)
        loss = self.loss_fn(pred, model_input.label)
        return (loss, pred)


class Tracer(torch.fx.Tracer):
    _leaf_module_names: List[str]

    def __init__(self, leaf_module_names: Optional[List[str]] = None) -> None:
        super().__init__()
        self._leaf_module_names = leaf_module_names or []

    def is_leaf_module(self, m: torch.nn.Module, module_qualified_name: str) -> bool:
        if module_qualified_name in self._leaf_module_names:
            return True
        return super().is_leaf_module(m, module_qualified_name)


class TrainPipelineBaseTest(unittest.TestCase):
    def setUp(self) -> None:
        self.device = torch.device("cuda:0")
        torch.backends.cudnn.allow_tf32 = False
        torch.backends.cuda.matmul.allow_tf32 = False

    # pyre-fixme[56]: Pyre was not able to infer the type of argument
    @unittest.skipIf(
        not torch.cuda.is_available(),
        "Not enough GPUs, this test requires at least one GPU",
    )
    def test_equal_to_non_pipelined(self) -> None:
        model_cpu = TestModule()
        model_gpu = TestModule().to(self.device)
        model_gpu.load_state_dict(model_cpu.state_dict())
        optimizer_cpu = optim.SGD(model_cpu.model.parameters(), lr=0.01)
        optimizer_gpu = optim.SGD(model_gpu.model.parameters(), lr=0.01)
        data = [
            ModelInputSimple(
                float_features=torch.rand((10,)),
                label=torch.randint(2, (1,), dtype=torch.float32),
            )
            for b in range(5)
        ]
        dataloader = iter(data)
        pipeline = TrainPipelineBase(model_gpu, optimizer_gpu, self.device)

        for batch in data[:-1]:
            optimizer_cpu.zero_grad()
            loss, pred = model_cpu(batch)
            loss.backward()
            optimizer_cpu.step()

            pred_gpu = pipeline.progress(dataloader)

            self.assertEqual(pred_gpu.device, self.device)
            # Results will be close but not exactly equal as one model is on CPU and other on GPU
            # If both were on GPU, the results will be exactly the same
            self.assertTrue(torch.isclose(pred_gpu.cpu(), pred))


class TrainPipelineSparseDistTest(TrainPipelineSparseDistTestBase):
    # pyre-fixme[56]: Pyre was not able to infer the type of argument
    @unittest.skipIf(
        not torch.cuda.is_available(),
        "Not enough GPUs, this test requires at least one GPU",
    )
    def test_feature_processed_ebc(self) -> None:
        # don't need weighted tables here
        self.weighted_tables = []

        sharder = cast(
            ModuleSharder[nn.Module], FeatureProcessedEmbeddingBagCollectionSharder()
        )

        class DummyWrapper(nn.Module):
            def __init__(self, sparse_arch):
                super().__init__()
                self.m = sparse_arch

            def forward(self, model_input) -> Tuple[torch.Tensor, torch.Tensor]:
                return self.m(model_input.idlist_features)

        max_feature_lengths = [10, 10, 12, 12]
        sparse_arch = DummyWrapper(
            create_module_and_freeze(
                tables=self.tables,
                device=self.device,
                use_fp_collection=False,
                max_feature_lengths=max_feature_lengths,
            )
        )
        compute_kernel = EmbeddingComputeKernel.FUSED.value
        module_sharding_plan = construct_module_sharding_plan(
            sparse_arch.m._fp_ebc,
            per_param_sharding={
                "table_0": table_wise(rank=0, compute_kernel=compute_kernel),
                "table_1": table_wise(rank=0, compute_kernel=compute_kernel),
                "table_2": table_wise(rank=0, compute_kernel=compute_kernel),
                "table_3": table_wise(rank=0, compute_kernel=compute_kernel),
            },
            local_size=1,
            world_size=1,
            device_type=self.device.type,
            sharder=sharder,
        )
        sharded_sparse_arch_no_pipeline = DistributedModelParallel(
            module=copy.deepcopy(sparse_arch),
            plan=ShardingPlan({"m._fp_ebc": module_sharding_plan}),
            env=ShardingEnv.from_process_group(self.pg),
            sharders=[sharder],
            device=self.device,
        )

        sharded_sparse_arch_pipeline = DistributedModelParallel(
            module=copy.deepcopy(sparse_arch),
            plan=ShardingPlan({"m._fp_ebc": module_sharding_plan}),
            env=ShardingEnv.from_process_group(self.pg),
            sharders=[sharder],
            device=self.device,
        )

        copy_state_dict(
            sharded_sparse_arch_no_pipeline.state_dict(),
            sharded_sparse_arch_pipeline.state_dict(),
        )

        data = self._generate_data(
            num_batches=5, batch_size=1, max_feature_lengths=max_feature_lengths
        )
        dataloader = iter(data)

        optimizer_no_pipeline = optim.SGD(
            sharded_sparse_arch_no_pipeline.parameters(), lr=0.1
        )
        optimizer_pipeline = optim.SGD(
            sharded_sparse_arch_pipeline.parameters(), lr=0.1
        )

        pipeline = TrainPipelineSparseDist(
            sharded_sparse_arch_pipeline,
            optimizer_pipeline,
            self.device,
        )

        for batch in data[:-2]:
            batch = batch.to(self.device)
            optimizer_no_pipeline.zero_grad()
            loss, pred = sharded_sparse_arch_no_pipeline(batch)
            loss.backward()
            optimizer_no_pipeline.step()

            pred_pipeline = pipeline.progress(dataloader)
            self.assertTrue(torch.equal(pred_pipeline.cpu(), pred.cpu()))

        self.assertEqual(len(pipeline._pipelined_modules), 1)
        self.assertIsInstance(
            pipeline._pipelined_modules[0],
            ShardedFeatureProcessedEmbeddingBagCollection,
        )

    def _setup_pipeline(
        self,
        sharder: EmbeddingBagCollectionSharder,
        execute_all_batches: bool,
        enable_fsdp: bool = False,
        unsharded_model: Optional[nn.Module] = None,
    ) -> TrainPipelineSparseDist[ModelInput, torch.Tensor]:
        if unsharded_model is None:
            unsharded_model = self._setup_model(enable_fsdp=enable_fsdp)

        distributed_model = DistributedModelParallel(
            unsharded_model,
            env=ShardingEnv.from_process_group(self.pg),
            init_data_parallel=False,
            device=self.device,
            sharders=[
                cast(
                    ModuleSharder[nn.Module],
                    sharder,
                )
            ],
        )
        optimizer_distributed = KeyedOptimizerWrapper(
            dict(in_backward_optimizer_filter(distributed_model.named_parameters())),
            lambda params: optim.SGD(params, lr=0.1),
        )
        return TrainPipelineSparseDist(
            model=distributed_model,
            optimizer=optimizer_distributed,
            device=self.device,
            execute_all_batches=execute_all_batches,
        )

    def _setup_cpu_model_and_opt(self) -> Tuple[TestSparseNN, optim.SGD]:
        cpu_model = TestSparseNN(
            tables=self.tables, weighted_tables=self.weighted_tables
        )
        cpu_optimizer = optim.SGD(cpu_model.parameters(), lr=0.1)
        return cpu_model, cpu_optimizer

    @unittest.skipIf(
        not torch.cuda.is_available(),
        "Not enough GPUs, this test requires at least one GPU",
    )
    @settings(max_examples=4, deadline=None)
    # pyre-ignore[56]
    @given(
        sharding_type=st.sampled_from(
            [
                ShardingType.TABLE_WISE.value,
                ShardingType.COLUMN_WISE.value,
            ]
        ),
        kernel_type=st.sampled_from(
            [
                EmbeddingComputeKernel.FUSED.value,
            ]
        ),
        execute_all_batches=st.booleans(),
    )
    def test_equal_to_non_pipelined(
        self,
        sharding_type: str,
        kernel_type: str,
        execute_all_batches: bool,
    ) -> None:
        """
        Checks that pipelined training is equivalent to non-pipelined training.
        """
        data = self._generate_data(
            num_batches=12,
            batch_size=32,
        )
        dataloader = iter(data)

        fused_params = {}
        fused_params_pipelined = {}

        model = self._setup_model()
        sharded_model, optim = self._generate_sharded_model_and_optimizer(
            model, sharding_type, kernel_type, fused_params
        )

        (
            sharded_model_pipelined,
            optim_pipelined,
        ) = self._generate_sharded_model_and_optimizer(
            model, sharding_type, kernel_type, fused_params_pipelined
        )
        copy_state_dict(
            sharded_model.state_dict(), sharded_model_pipelined.state_dict()
        )

        pipeline = TrainPipelineSparseDist(
            model=sharded_model_pipelined,
            optimizer=optim_pipelined,
            device=self.device,
            execute_all_batches=execute_all_batches,
        )
        if not execute_all_batches:
            data = data[:-2]

        for batch in data:
            # Forward + backward w/o pipelining
            batch = batch.to(self.device)
            optim.zero_grad()
            loss, pred = sharded_model(batch)
            loss.backward()
            optim.step()

            # Forward + backward w/ pipelining
            pred_pipeline = pipeline.progress(dataloader)
            torch.testing.assert_close(pred, pred_pipeline)

        self.assertRaises(StopIteration, pipeline.progress, dataloader)

    @unittest.skipIf(
        not torch.cuda.is_available(),
        "Not enough GPUs, this test requires at least one GPU",
    )
    # pyre-ignore[56]
    @given(execute_all_batches=st.booleans())
    @settings(verbosity=Verbosity.verbose, max_examples=2, deadline=None)
    def test_pipelining_fsdp_pre_trace(self, execute_all_batches: bool) -> None:
        unsharded_model = self._setup_model(enable_fsdp=True)
        leaf_module_names = []
        for i, _ in unsharded_model.named_children():
            leaf_module_names.append(i)
        # Simulate a corner case where we trace into the child module
        # so direct children is not part of the graph. This will break the
        # original pipelining logic, because the leaf module is only the direct
        # children, and when the root node calls directly into child's child.
        # It was broken because the child'child is a FSDP module and it
        # breaks because FSDP is not trace-able
        leaf_module_names.remove("over")
        leaf_module_names.append("over.dhn_arch")
        tracer = Tracer(leaf_module_names=leaf_module_names)
        graph = tracer.trace(unsharded_model)

        traced_model = torch.fx.GraphModule(unsharded_model, graph)
        pipeline = self._setup_pipeline(
            TestEBCSharder(
                sharding_type=ShardingType.TABLE_WISE.value,
                kernel_type=EmbeddingComputeKernel.FUSED.value,
            ),
            execute_all_batches,
            enable_fsdp=True,
            unsharded_model=traced_model,
        )
        cpu_model, cpu_optimizer = self._setup_cpu_model_and_opt()
        data = self._generate_data()

        dataloader = iter(data)
        if not execute_all_batches:
            data = data[:-2]

        for batch in data:
            cpu_optimizer.zero_grad()
            loss, pred = cpu_model(batch)
            loss.backward()
            cpu_optimizer.step()

            pred_gpu = pipeline.progress(dataloader)

            self.assertEqual(len(pipeline._pipelined_modules), 2)
            self.assertEqual(pred_gpu.device, self.device)
            self.assertEqual(pred_gpu.cpu().size(), pred.size())

    # pyre-ignore
    @unittest.skipIf(
        not torch.cuda.is_available(),
        "Not enough GPUs, this test requires at least one GPU",
    )
    def test_model_detach_during_train(self) -> None:
        """
        Test the scenario in which:
        1) Model training with pipeline.progress()
        2) Mid-training, model is detached
        3) Check that fwd of detached model is same as non-pipelined model
        4) Pipeline progress() re-attaches the model and we can continue progressing
        """
        data = self._generate_data(
            num_batches=7,
            batch_size=32,
        )
        dataloader = iter(data)

        sharding_type = ShardingType.TABLE_WISE.value
        kernel_type = EmbeddingComputeKernel.FUSED.value
        fused_params = {}

        model = self._setup_model()
        sharded_model, optim = self._generate_sharded_model_and_optimizer(
            model, sharding_type, kernel_type, fused_params
        )

        (
            sharded_model_pipelined,
            optim_pipelined,
        ) = self._generate_sharded_model_and_optimizer(
            model, sharding_type, kernel_type, fused_params
        )
        copy_state_dict(
            sharded_model.state_dict(), sharded_model_pipelined.state_dict()
        )

        pipeline = TrainPipelineSparseDist(
            model=sharded_model_pipelined,
            optimizer=optim_pipelined,
            device=self.device,
            execute_all_batches=True,
        )

        for i in range(3):
            batch = data[i]
            # Forward + backward w/o pipelining
            batch = batch.to(self.device)
            optim.zero_grad()
            loss, pred = sharded_model(batch)
            loss.backward()
            optim.step()

            pred_pipelined = pipeline.progress(dataloader)
            self.assertTrue(torch.equal(pred, pred_pipelined))

        # Check internal states
        ebcs = [
            sharded_model_pipelined.module.sparse.ebc,
            sharded_model_pipelined.module.sparse.weighted_ebc,
        ]
        for ebc in ebcs:
            self.assertIsInstance(ebc.forward, PipelinedForward)

        detached_model = pipeline.detach()

        # Check internal states
        for ebc in ebcs:
            self.assertNotIsInstance(ebc.forward, PipelinedForward)

        # Check fwd of detached model is same as non-pipelined model
        with torch.no_grad():
            batch = data[3].to(self.device)
            _, detached_out = detached_model(batch)
            _, out = sharded_model(batch)
            self.assertTrue(torch.equal(detached_out, out))

        # Check that pipeline re-attaches the model again without issues
        for i in range(3, 7):
            batch = data[i]
            # Forward + backward w/o pipelining
            batch = batch.to(self.device)
            optim.zero_grad()
            loss, pred = sharded_model(batch)
            loss.backward()
            optim.step()

            pred_pipelined = pipeline.progress(dataloader)
            self.assertTrue(torch.equal(pred, pred_pipelined))

        for ebc in ebcs:
            self.assertIsInstance(ebc.forward, PipelinedForward)

        # Check pipeline exhausted
        self.assertRaises(StopIteration, pipeline.progress, dataloader)

    # pyre-ignore
    @unittest.skipIf(
        not torch.cuda.is_available(),
        "Not enough GPUs, this test requires at least one GPU",
    )
    def test_model_detach_after_train(self) -> None:
        """
        Test the scenario in which:
        1) Model training with pipeline.progress()
        2) Pipeline exhausts dataloader and raises StopIteration
        4) Model is detached
        5) Check that fwd of detached model is same as non-pipelined model
        6) Pipeline progress() with new dataloader re-attaches model
        """
        data = self._generate_data(
            num_batches=7,
            batch_size=32,
        )
        dataloader = iter(data)

        sharding_type = ShardingType.TABLE_WISE.value
        kernel_type = EmbeddingComputeKernel.FUSED.value
        fused_params = {}

        model = self._setup_model()
        sharded_model, optim = self._generate_sharded_model_and_optimizer(
            model, sharding_type, kernel_type, fused_params
        )

        (
            sharded_model_pipelined,
            optim_pipelined,
        ) = self._generate_sharded_model_and_optimizer(
            model, sharding_type, kernel_type, fused_params
        )
        copy_state_dict(
            sharded_model.state_dict(), sharded_model_pipelined.state_dict()
        )

        pipeline = TrainPipelineSparseDist(
            model=sharded_model_pipelined,
            optimizer=optim_pipelined,
            device=self.device,
            execute_all_batches=True,
        )

        for i in range(7):
            batch = data[i]
            # Forward + backward w/o pipelining
            batch = batch.to(self.device)
            optim.zero_grad()
            loss, pred = sharded_model(batch)
            loss.backward()
            optim.step()

            pred_pipelined = pipeline.progress(dataloader)
            self.assertTrue(torch.equal(pred, pred_pipelined))

        # Check pipeline exhausted
        self.assertRaises(StopIteration, pipeline.progress, dataloader)

        detached_model = pipeline.detach()

        # Check internal states
        ebcs = [
            sharded_model_pipelined.module.sparse.ebc,
            sharded_model_pipelined.module.sparse.weighted_ebc,
        ]
        for ebc in ebcs:
            self.assertNotIsInstance(ebc.forward, PipelinedForward)

        # Check fwd of detached model is same as non-pipelined model
        with torch.no_grad():
            for i in range(2):
                batch = data[i].to(self.device)
                _, detached_out = detached_model(batch)
                _, out = sharded_model(batch)
                self.assertTrue(torch.equal(detached_out, out))

        # Provide new loaded dataloader and check model is re-attached
        data = self._generate_data(
            num_batches=4,
            batch_size=32,
        )
        dataloader = iter(data)

        for i in range(4):
            batch = data[i]
            batch = batch.to(self.device)
            optim.zero_grad()
            loss, pred = sharded_model(batch)
            loss.backward()
            optim.step()

            pred_pipelined = pipeline.progress(dataloader)
            self.assertTrue(torch.equal(pred, pred_pipelined))

        # Check pipeline exhausted
        self.assertRaises(StopIteration, pipeline.progress, dataloader)

    # pyre-fixme[56]: Pyre was not able to infer the type of argument
    @unittest.skipIf(
        not torch.cuda.is_available(),
        "Not enough GPUs, this test requires at least one GPU",
    )
    def test_multi_dataloader_pipelining(self) -> None:
        pipeline = self._setup_pipeline(
            sharder=TestEBCSharder(
                sharding_type=ShardingType.TABLE_WISE.value,
                kernel_type=EmbeddingComputeKernel.FUSED.value,
            ),
            execute_all_batches=True,
        )
        cpu_model, cpu_optimizer = self._setup_cpu_model_and_opt()
        data = self._generate_data(num_batches=7)

        cpu_preds = []
        for batch in data:
            cpu_optimizer.zero_grad()
            loss, pred = cpu_model(batch)
            loss.backward()
            cpu_optimizer.step()
            cpu_preds.append(pred)

        dataloaders = [iter(data[:-3]), iter(data[-3:-2]), iter(data[-2:])]
        gpu_preds = []
        for dataloader in dataloaders:
            while True:
                try:
                    pred = pipeline.progress(dataloader)
                    self.assertEqual(pred.device, self.device)
                    self.assertEqual(len(pipeline._pipelined_modules), 2)
                    gpu_preds.append(pred.cpu())
                except StopIteration:
                    break

        self.assertEqual(len(pipeline._pipelined_modules), 2)
        self.assertEqual(len(cpu_preds), len(gpu_preds))
        self.assertTrue(
            all(
                cpu_pred.size() == gpu_pred.size()
                for cpu_pred, gpu_pred in zip(cpu_preds, gpu_preds)
            )
        )


class EmbeddingTrainPipelineTest(TrainPipelineSparseDistTestBase):
    @unittest.skipIf(
        not torch.cuda.is_available(),
        "Not enough GPUs, this test requires at least one GPU",
    )
    @settings(max_examples=4, deadline=None)
    # pyre-ignore[56]
    @given(
        start_batch=st.sampled_from([0, 6]),
        stash_gradients=st.booleans(),
        sharding_type=st.sampled_from(
            [
                ShardingType.TABLE_WISE.value,
                ShardingType.ROW_WISE.value,
            ]
        ),
        kernel_type=st.sampled_from(
            [
                EmbeddingComputeKernel.FUSED.value,
            ]
        ),
    )
    def test_equal_to_non_pipelined(
        self,
        start_batch: int,
        stash_gradients: bool,
        sharding_type: str,
        kernel_type: str,
    ) -> None:
        """
        Checks that pipelined training is equivalent to non-pipelined training.
        """
        torch.autograd.set_detect_anomaly(True)
        data = self._generate_data(
            num_batches=12,
            batch_size=32,
        )
        dataloader = iter(data)

        fused_params = {
            "stochastic_rounding": False,
        }
        fused_params_pipelined = {
            **fused_params,
        }

        model = self._setup_model()
        sharded_model, optim = self._generate_sharded_model_and_optimizer(
            model, sharding_type, kernel_type, fused_params
        )

        (
            sharded_model_pipelined,
            optim_pipelined,
        ) = self._generate_sharded_model_and_optimizer(
            model, sharding_type, kernel_type, fused_params_pipelined
        )
        copy_state_dict(
            sharded_model.state_dict(), sharded_model_pipelined.state_dict()
        )

        pipeline = TrainPipelineSemiSync(
            model=sharded_model_pipelined,
            optimizer=optim_pipelined,
            device=self.device,
            execute_all_batches=True,
            start_batch=start_batch,
            stash_gradients=stash_gradients,
        )

        prior_sparse_out = sharded_model._dmp_wrapped_module.sparse_forward(
            data[0].to(self.device)
        )
        prior_batch = data[0].to(self.device)
        prior_stashed_grads = None
        batch_index = 0
        sparse_out = None
        for batch in data[1:]:
            batch_index += 1
            # Forward + backward w/o pipelining
            batch = batch.to(self.device)

            loss, pred = sharded_model._dmp_wrapped_module.dense_forward(
                prior_batch, prior_sparse_out
            )
            if batch_index - 1 >= start_batch:
                sparse_out = sharded_model._dmp_wrapped_module.sparse_forward(batch)

            loss.backward()

            stashed_grads = None
            if batch_index - 1 >= start_batch and stash_gradients:
                stashed_grads = []
                for param in optim.param_groups[0]["params"]:
                    stashed_grads.append(
                        param.grad.clone() if param.grad is not None else None
                    )
                    param.grad = None

            if prior_stashed_grads is not None:
                for param, stashed_grad in zip(
                    optim.param_groups[0]["params"], prior_stashed_grads
                ):
                    param.grad = stashed_grad
            optim.step()
            optim.zero_grad()

            if batch_index - 1 < start_batch:
                sparse_out = sharded_model._dmp_wrapped_module.sparse_forward(batch)

            prior_stashed_grads = stashed_grads
            prior_batch = batch
            prior_sparse_out = sparse_out
            # Forward + backward w/ pipelining
            pred_pipeline = pipeline.progress(dataloader)

            if batch_index >= start_batch:
                self.assertTrue(
                    pipeline.is_semi_sync(), msg="pipeline is not semi_sync"
                )
            else:
                self.assertFalse(pipeline.is_semi_sync(), msg="pipeline is semi_sync")
            self.assertTrue(
                torch.equal(pred, pred_pipeline),
                msg=f"batch {batch_index} doesn't match",
            )

        # one more batch
        pred_pipeline = pipeline.progress(dataloader)
        self.assertRaises(StopIteration, pipeline.progress, dataloader)


class PrefetchTrainPipelineSparseDistTest(TrainPipelineSparseDistTestBase):
    @unittest.skipIf(
        not torch.cuda.is_available(),
        "Not enough GPUs, this test requires at least one GPU",
    )
    @settings(max_examples=4, deadline=None)
    # pyre-ignore[56]
    @given(
        execute_all_batches=st.booleans(),
        weight_precision=st.sampled_from(
            [
                DataType.FP16,
                DataType.FP32,
            ]
        ),
        cache_precision=st.sampled_from(
            [
                DataType.FP16,
                DataType.FP32,
            ]
        ),
        load_factor=st.sampled_from(
            [
                0.2,
                0.4,
                0.6,
            ]
        ),
        sharding_type=st.sampled_from(
            [
                ShardingType.TABLE_WISE.value,
                ShardingType.ROW_WISE.value,
                ShardingType.COLUMN_WISE.value,
            ]
        ),
        kernel_type=st.sampled_from(
            [
                EmbeddingComputeKernel.FUSED_UVM_CACHING.value,
            ]
        ),
    )
    def test_equal_to_non_pipelined(
        self,
        execute_all_batches: bool,
        weight_precision: DataType,
        cache_precision: DataType,
        load_factor: float,
        sharding_type: str,
        kernel_type: str,
    ) -> None:
        """
        Checks that pipelined training is equivalent to non-pipelined training.
        """
        mixed_precision: bool = weight_precision != cache_precision
        self._set_table_weights_precision(weight_precision)
        data = self._generate_data(
            num_batches=12,
            batch_size=32,
        )
        dataloader = iter(data)

        fused_params = {
            "cache_load_factor": load_factor,
            "cache_precision": cache_precision,
            "stochastic_rounding": False,  # disable non-deterministic behavior when converting fp32<->fp16
        }
        fused_params_pipelined = {
            **fused_params,
            "prefetch_pipeline": True,
        }

        model = self._setup_model()
        sharded_model, optim = self._generate_sharded_model_and_optimizer(
            model, sharding_type, kernel_type, fused_params
        )

        (
            sharded_model_pipelined,
            optim_pipelined,
        ) = self._generate_sharded_model_and_optimizer(
            model, sharding_type, kernel_type, fused_params_pipelined
        )
        copy_state_dict(
            sharded_model.state_dict(), sharded_model_pipelined.state_dict()
        )

        pipeline = PrefetchTrainPipelineSparseDist(
            model=sharded_model_pipelined,
            optimizer=optim_pipelined,
            device=self.device,
            execute_all_batches=execute_all_batches,
        )

        if not execute_all_batches:
            data = data[:-3]

        for batch in data:
            # Forward + backward w/o pipelining
            batch = batch.to(self.device)
            optim.zero_grad()
            loss, pred = sharded_model(batch)
            loss.backward()
            optim.step()

            # Forward + backward w/ pipelining
            pred_pipeline = pipeline.progress(dataloader)

            if not mixed_precision:
                # Rounding error is expected when using different precisions for weights and cache
                self.assertTrue(torch.equal(pred, pred_pipeline))
            else:
                torch.testing.assert_close(pred, pred_pipeline)


class DataLoadingThreadTest(unittest.TestCase):
    def test_fetch_data(self) -> None:
        data = []
        for i in range(7):
            data.append(torch.tensor([i]))
        data_iter = iter(data)
        data_loader = DataLoadingThread(torch.device("cpu"), data_iter, True)
        data_loader.start()
        for i in range(7):
            item = data_loader.get_next_batch()
            self.assertEqual(item.item(), i)

        self.assertIsNone(data_loader.get_next_batch(False))
        with self.assertRaises(StopIteration):
            data_loader.get_next_batch(True)
        data_loader.stop()


class EvalPipelineSparseDistTest(unittest.TestCase):
    def test_processing(self) -> None:
        mock_model = MagicMock()

        def model_side_effect(
            item: Pipelineable,
        ) -> Tuple[Optional[Pipelineable], Pipelineable]:
            return (None, item)

        mock_model.side_effect = model_side_effect
        mock_optimizer = MagicMock()

        class MockPipeline(EvalPipelineSparseDist):
            def __init__(self, model, optimizer, device: torch.device) -> None:
                super().__init__(model, optimizer, device)

            def _init_pipelined_modules(
                self,
                item: Pipelineable,
                context: TrainPipelineContext,
                pipelined_forward: Type[PipelinedForward],
            ) -> None:
                pass

            def _start_sparse_data_dist(
                self, item: Pipelineable, context: TrainPipelineContext
            ) -> None:
                pass

            def _wait_sparse_data_dist(self, context: TrainPipelineContext) -> None:
                pass

        pipeline = MockPipeline(mock_model, mock_optimizer, torch.device("cpu"))

        data = []
        for i in range(7):
            data.append(torch.tensor([i]))
        data_iter = iter(data)

        for i in range(7):
            item = pipeline.progress(data_iter)
            self.assertEqual(item.item(), i)

        self.assertRaises(StopIteration, pipeline.progress, data_iter)


class StagedTrainPipelineTest(TrainPipelineSparseDistTestBase):
    # pyre-ignore
    @unittest.skipIf(
        not torch.cuda.is_available(),
        "Not enough GPUs, this test requires at least one GPU",
    )
    def test_pipelining(self) -> None:
        model = self._setup_model()

        sharding_type = ShardingType.TABLE_WISE.value
        kernel_type = EmbeddingComputeKernel.FUSED.value

        sharded_model, optim = self._generate_sharded_model_and_optimizer(
            model, sharding_type, kernel_type
        )
        (
            sharded_model_pipelined,
            optim_pipelined,
        ) = self._generate_sharded_model_and_optimizer(
            model, sharding_type, kernel_type
        )

        copy_state_dict(
            sharded_model.state_dict(), sharded_model_pipelined.state_dict()
        )

        num_batches = 12
        data = self._generate_data(
            num_batches=num_batches,
            batch_size=32,
        )

        non_pipelined_outputs = []
        for batch in data:
            batch = batch.to(self.device)
            optim.zero_grad()
            loss, pred = sharded_model(batch)
            loss.backward()
            optim.step()
            non_pipelined_outputs.append(pred)

        def gpu_preproc(x: StageOut) -> StageOut:
            return x

        sdd = SparseDataDistUtil[ModelInput](
            model=sharded_model_pipelined,
            stream=torch.cuda.Stream(),
            apply_jit=False,
        )

        pipeline_stages = [
            PipelineStage(
                name="data_copy",
                runnable=partial(get_h2d_func, device=self.device),
                stream=torch.cuda.Stream(),
            ),
            PipelineStage(
                name="gpu_preproc",
                runnable=gpu_preproc,
                stream=torch.cuda.Stream(),
            ),
            PipelineStage(
                name="gpu_preproc_1",
                runnable=gpu_preproc,
                stream=torch.cuda.Stream(),
            ),
            PipelineStage(
                name="gpu_preproc_2",
                runnable=gpu_preproc,
                stream=torch.cuda.Stream(),
            ),
            PipelineStage(
                name="start_sparse_data_dist",
                runnable=sdd.start_sparse_data_dist,
                stream=sdd.stream,
                fill_callback=sdd.wait_sparse_data_dist,
            ),
        ]
        pipeline = StagedTrainPipeline(
            pipeline_stages=pipeline_stages, compute_stream=torch.cuda.current_stream()
        )
        dataloader = iter(data)

        pipelined_out = []
        num_batches_processed = 0

        while model_in := pipeline.progress(dataloader):
            num_batches_processed += 1
            optim_pipelined.zero_grad()
            loss, pred = sharded_model_pipelined(model_in)
            loss.backward()
            optim_pipelined.step()
            pipelined_out.append(pred)

        self.assertEqual(num_batches_processed, num_batches)

        self.assertEqual(len(pipelined_out), len(non_pipelined_outputs))
        for out, ref_out in zip(pipelined_out, non_pipelined_outputs):
            torch.testing.assert_close(out, ref_out)

    # pyre-ignore
    @unittest.skipIf(
        not torch.cuda.is_available(),
        "Not enough GPUs, this test requires at least one GPU",
    )
    def test_pipeline_flush(self) -> None:
        model = self._setup_model()

        sharding_type = ShardingType.TABLE_WISE.value
        kernel_type = EmbeddingComputeKernel.FUSED.value

        (
            sharded_model_pipelined,
            optim_pipelined,
        ) = self._generate_sharded_model_and_optimizer(
            model, sharding_type, kernel_type
        )

        def gpu_preproc(x: StageOut) -> StageOut:
            return x

        sdd = SparseDataDistUtil[ModelInput](
            model=sharded_model_pipelined,
            stream=torch.cuda.Stream(),
            apply_jit=False,
        )

        pipeline_stages = [
            PipelineStage(
                name="data_copy",
                runnable=partial(get_h2d_func, device=self.device),
                stream=torch.cuda.Stream(),
            ),
            PipelineStage(
                name="gpu_preproc",
                runnable=gpu_preproc,
                stream=torch.cuda.Stream(),
            ),
            PipelineStage(
                name="start_sparse_data_dist",
                runnable=sdd.start_sparse_data_dist,
                stream=sdd.stream,
                fill_callback=sdd.wait_sparse_data_dist,
            ),
        ]

        flush_end_called: int = 0

        def on_flush_end() -> None:
            nonlocal flush_end_called
            flush_end_called += 1

        pipeline = StagedTrainPipeline(
            pipeline_stages=pipeline_stages,
            compute_stream=torch.cuda.current_stream(),
            on_flush_end=on_flush_end,
        )
        self.assertEqual(pipeline._flushing, False)

        data = self._generate_data(
            num_batches=10,
            batch_size=32,
        )
        dataloader = iter(data)

        # Run pipeline for 1 iteration, now internal state should be:
        # pipeline._stage_outputs = [stage 2 output, stage 1 output, stage 0 output]
        # and we exhaust 4 batches from dataloader (3 + 1 in _fill_pipeline)
        out = pipeline.progress(dataloader)
        self.assertIsNotNone(out)

        # Flush pipeline
        pipeline.set_flush(True)

        # Run pipeline for 3 iterations
        # Iteration 1: pipeline returns output from second batch
        # Iteration 2: pipeline returns output from third batch
        # Iteration 3: pipeline returns output from fourth batch
        for _ in range(3):
            out = pipeline.progress(dataloader)
            self.assertIsNotNone(out)

        # Flush end not reached
        self.assertEqual(flush_end_called, 0)

        # After this iteration, pipeline has been completely flushed
        out = pipeline.progress(dataloader)
        self.assertEqual(flush_end_called, 1)
        # output shouldn't be None as we restart pipeline
        # this should be output from fifth batch
        self.assertIsNotNone(out)

        # Pipeline internal state
        self.assertEqual(pipeline._flushing, False)
        self.assertIsNotNone(pipeline._stage_outputs[0])
        self.assertIsNotNone(pipeline._stage_outputs[1])
        self.assertIsNotNone(pipeline._stage_outputs[2])

        # Check that we get 5 more iterations before pipeline exhausts all data
        for _ in range(5):
            out = pipeline.progress(dataloader)
            self.assertIsNotNone(out)

        # Check that pipeline has exhausted all data
        out = pipeline.progress(dataloader)
        self.assertIsNone(out)

        # Flush end not called this time
        self.assertEqual(flush_end_called, 1)

    # pyre-ignore
    @unittest.skipIf(
        not torch.cuda.is_available(),
        "Not enough GPUs, this test requires at least one GPU",
    )
    def test_model_detach(self) -> None:
        model = self._setup_model()

        sharding_type = ShardingType.TABLE_WISE.value
        fused_params = {}
        kernel_type = EmbeddingComputeKernel.FUSED.value

        sharded_model, optim = self._generate_sharded_model_and_optimizer(
            model, sharding_type, kernel_type, fused_params
        )

        (
            sharded_model_pipelined,
            optim_pipelined,
        ) = self._generate_sharded_model_and_optimizer(
            model, sharding_type, kernel_type
        )

        copy_state_dict(
            sharded_model.state_dict(), sharded_model_pipelined.state_dict()
        )

        sdd = SparseDataDistUtil[ModelInput](
            model=sharded_model_pipelined,
            stream=torch.cuda.Stream(),
            apply_jit=False,
        )

        pipeline_stages = [
            PipelineStage(
                name="data_copy",
                runnable=partial(get_h2d_func, device=self.device),
                stream=torch.cuda.Stream(),
            ),
            PipelineStage(
                name="start_sparse_data_dist",
                runnable=sdd.start_sparse_data_dist,
                stream=sdd.stream,
                fill_callback=sdd.wait_sparse_data_dist,
            ),
        ]

        pipeline = StagedTrainPipeline(
            pipeline_stages=pipeline_stages,
            compute_stream=torch.cuda.current_stream(),
        )

        data = self._generate_data(
            num_batches=12,
            batch_size=32,
        )
        dataloader = iter(data)

        for i in range(5):
            batch = data[i]
            # Forward + backward w/o pipelining
            batch = batch.to(self.device)
            optim.zero_grad()
            loss, pred = sharded_model(batch)
            loss.backward()
            optim.step()

            model_in = pipeline.progress(dataloader)
            optim_pipelined.zero_grad()
            loss_pred, pred_pipelined = sharded_model_pipelined(model_in)
            loss_pred.backward()
            optim_pipelined.step()

            self.assertTrue(torch.equal(pred, pred_pipelined))

        # Check internal states
        ebcs = [
            sharded_model_pipelined.module.sparse.ebc,
            sharded_model_pipelined.module.sparse.weighted_ebc,
        ]
        for ebc in ebcs:
            self.assertIsInstance(ebc.forward, PipelinedForward)
        self.assertEqual(len(sharded_model_pipelined._forward_hooks.items()), 1)

        detached_model = sdd.detach()

        # Check internal states
        for ebc in ebcs:
            self.assertNotIsInstance(ebc.forward, PipelinedForward)
        self.assertEqual(len(sharded_model_pipelined._forward_hooks.items()), 0)

        # Check we can run backward and optimizer ond detached model
        batch = data[5].to(self.device)
        loss_detached, detached_out = detached_model(batch)
        loss_sharded, out = sharded_model(batch)
        self.assertTrue(torch.equal(detached_out, out))
        loss_detached.backward()
        loss_sharded.backward()
        optim.step()
        optim_pipelined.step()

        # Check fwd of detached model is same as non-pipelined model
        with torch.no_grad():
            batch = data[6].to(self.device)
            _, detached_out = detached_model(batch)
            _, out = sharded_model(batch)
            self.assertTrue(torch.equal(detached_out, out))

        # Check that pipeline re-attaches the model again without issues
        for i in range(5, 12):
            batch = data[i]
            # Forward + backward w/o pipelining
            batch = batch.to(self.device)
            optim.zero_grad()
            loss, pred = sharded_model(batch)
            loss.backward()
            optim.step()

            model_in = pipeline.progress(dataloader)
            optim_pipelined.zero_grad()
            loss_pred, pred_pipelined = sharded_model_pipelined(model_in)
            loss_pred.backward()
            optim_pipelined.step()

            self.assertTrue(torch.equal(pred, pred_pipelined))

        for ebc in ebcs:
            self.assertIsInstance(ebc.forward, PipelinedForward)
        self.assertEqual(len(sharded_model_pipelined._forward_hooks.items()), 1)

        # Check pipeline exhausted
        preproc_input = pipeline.progress(dataloader)
        self.assertIsNone(preproc_input)
