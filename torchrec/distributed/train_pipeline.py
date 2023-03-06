#!/usr/bin/env python3
# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
#
# This source code is licensed under the BSD-style license found in the
# LICENSE file in the root directory of this source tree.

import abc
import logging
from typing import cast, Dict, Generic, Iterator, List, Optional, Tuple, TypeVar

import torch
from torch.autograd.profiler import record_function
from torchrec.distributed.model_parallel import ShardedModule
from torchrec.distributed.pipeline_utils import (
    _rewrite_model,
    _start_data_dist,
    _to_device,
    _wait_for_batch,
    TrainPipelineContext,
)
from torchrec.streamable import Pipelineable

logger: logging.Logger = logging.getLogger(__name__)


In = TypeVar("In", bound=Pipelineable)
Out = TypeVar("Out")


class TrainPipeline(abc.ABC, Generic[In, Out]):
    @abc.abstractmethod
    def progress(self, dataloader_iter: Iterator[In]) -> Out:
        pass


class TrainPipelineBase(TrainPipeline[In, Out]):
    """
    This class runs training iterations using a pipeline of two stages, each as a CUDA
    stream, namely, the current (default) stream and `self._memcpy_stream`. For each
    iteration, `self._memcpy_stream` moves the input from host (CPU) memory to GPU
    memory, and the default stream runs forward, backward, and optimization.
    """

    def __init__(
        self,
        model: torch.nn.Module,
        optimizer: torch.optim.Optimizer,
        device: torch.device,
    ) -> None:
        self._model = model
        self._optimizer = optimizer
        self._device = device
        self._memcpy_stream: Optional[torch.cuda.streams.Stream] = (
            torch.cuda.Stream() if device.type == "cuda" else None
        )
        self._cur_batch: Optional[In] = None
        self._connected = False

    def _connect(self, dataloader_iter: Iterator[In]) -> None:
        cur_batch = next(dataloader_iter)
        self._cur_batch = cur_batch
        with torch.cuda.stream(self._memcpy_stream):
            self._cur_batch = _to_device(cur_batch, self._device, non_blocking=True)
        self._connected = True

    def progress(self, dataloader_iter: Iterator[In]) -> Out:
        if not self._connected:
            self._connect(dataloader_iter)

        # Fetch next batch
        with record_function("## next_batch ##"):
            next_batch = next(dataloader_iter)
        cur_batch = self._cur_batch
        assert cur_batch is not None

        if self._model.training:
            with record_function("## zero_grad ##"):
                self._optimizer.zero_grad()

        with record_function("## wait_for_batch ##"):
            _wait_for_batch(cur_batch, self._memcpy_stream)

        with record_function("## forward ##"):
            (losses, output) = self._model(cur_batch)

        if self._model.training:
            with record_function("## backward ##"):
                torch.sum(losses, dim=0).backward()

        # Copy the next batch to GPU
        self._cur_batch = cur_batch = next_batch
        with record_function("## copy_batch_to_gpu ##"):
            with torch.cuda.stream(self._memcpy_stream):
                self._cur_batch = _to_device(cur_batch, self._device, non_blocking=True)

        # Update
        if self._model.training:
            with record_function("## optimizer ##"):
                self._optimizer.step()

        return output


class TrainPipelineSparseDist(TrainPipeline[In, Out]):
    """
    This pipeline overlaps device transfer, and `ShardedModule.input_dist()` with
    forward and backward. This helps hide the all2all latency while preserving the
    training forward / backward ordering.

    stage 3: forward, backward - uses default CUDA stream
    stage 2: ShardedModule.input_dist() - uses data_dist CUDA stream
    stage 1: device transfer - uses memcpy CUDA stream

    `ShardedModule.input_dist()` is only done for top-level modules in the call graph.
    To be considered a top-level module, a module can only depend on 'getattr' calls on
    input.

    Input model must be symbolically traceable with the exception of `ShardedModule` and
    `DistributedDataParallel` modules.
    """

    synced_pipeline_id: Dict[int, int] = {}

    def __init__(
        self,
        model: torch.nn.Module,
        optimizer: torch.optim.Optimizer,
        device: torch.device,
    ) -> None:
        self._model = model
        self._optimizer = optimizer
        self._device = device
        # use two data streams to support two concurrent batches
        if device.type == "cuda":
            self._memcpy_stream: Optional[
                torch.cuda.streams.Stream
            ] = torch.cuda.Stream()
            self._data_dist_stream: Optional[
                torch.cuda.streams.Stream
            ] = torch.cuda.Stream()
        else:
            self._memcpy_stream: Optional[torch.cuda.streams.Stream] = None
            self._data_dist_stream: Optional[torch.cuda.streams.Stream] = None
        self._batch_i: Optional[In] = None
        self._batch_ip1: Optional[In] = None
        self._batch_ip2: Optional[In] = None
        self._connected = False
        self._context = TrainPipelineContext()
        self._pipelined_modules: List[ShardedModule] = []

    def _connect(self, dataloader_iter: Iterator[In]) -> None:
        # batch 1
        with torch.cuda.stream(self._memcpy_stream):
            batch_i = next(dataloader_iter)
            self._batch_i = batch_i = _to_device(
                batch_i, self._device, non_blocking=True
            )
            # Try to pipeline input data dist.
            self._pipelined_modules = _rewrite_model(
                self._model, self._context, self._data_dist_stream
            )

        with torch.cuda.stream(self._data_dist_stream):
            _wait_for_batch(batch_i, self._memcpy_stream)
            _start_data_dist(self._pipelined_modules, batch_i, self._context)

        # batch 2
        with torch.cuda.stream(self._memcpy_stream):
            batch_ip1 = next(dataloader_iter)
            self._batch_ip1 = batch_ip1 = _to_device(
                batch_ip1, self._device, non_blocking=True
            )
        self._connected = True
        self.__class__.synced_pipeline_id[id(self._model)] = id(self)

    def progress(self, dataloader_iter: Iterator[In]) -> Out:
        if not self._connected:
            self._connect(dataloader_iter)
        elif self.__class__.synced_pipeline_id.get(id(self._model), None) != id(self):
            self._sync_pipeline()
            self.__class__.synced_pipeline_id[id(self._model)] = id(self)

        if self._model.training:
            with record_function("## zero_grad ##"):
                self._optimizer.zero_grad()

        with record_function("## copy_batch_to_gpu ##"):
            with torch.cuda.stream(self._memcpy_stream):
                batch_ip2 = next(dataloader_iter)
                self._batch_ip2 = batch_ip2 = _to_device(
                    batch_ip2, self._device, non_blocking=True
                )
        batch_i = cast(In, self._batch_i)
        batch_ip1 = cast(In, self._batch_ip1)

        with record_function("## wait_for_batch ##"):
            _wait_for_batch(batch_i, self._data_dist_stream)

        # Forward
        with record_function("## forward ##"):
            # if using multiple streams (ie. CUDA), create an event in default stream
            # before starting forward pass
            if self._data_dist_stream:
                event = torch.cuda.current_stream().record_event()
            (losses, output) = cast(Tuple[torch.Tensor, Out], self._model(batch_i))

        # Data Distribution
        with record_function("## sparse_data_dist ##"):
            with torch.cuda.stream(self._data_dist_stream):
                _wait_for_batch(batch_ip1, self._memcpy_stream)
                # Ensure event in default stream has been called before
                # starting data dist
                if self._data_dist_stream:
                    # pyre-ignore [61]: Local variable `event` is undefined, or not always defined
                    self._data_dist_stream.wait_event(event)
                _start_data_dist(self._pipelined_modules, batch_ip1, self._context)

        if self._model.training:
            # Backward
            with record_function("## backward ##"):
                torch.sum(losses, dim=0).backward()

            # Update
            with record_function("## optimizer ##"):
                self._optimizer.step()

        self._batch_i = batch_ip1
        self._batch_ip1 = batch_ip2

        return output

    def _sync_pipeline(self) -> None:
        """
        Syncs `PipelinedForward` for sharded modules with context and dist stream of the
        current train pipeline. Used when switching between train pipelines for the same
        model.
        """
        for module in self._pipelined_modules:
            module.forward._context = self._context
            module.forward._dist_stream = self._data_dist_stream
