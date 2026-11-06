"""A trusted program for Gboard ACT model training."""

import base64
from collections.abc import Callable
from collections.abc import Sequence
import concurrent.futures
import contextlib
import json
import math
import os
import queue
import threading
import time
from typing import Any
import zipfile

from absl import logging
from fcp.confidentialcompute.python import accounting
from fcp.confidentialcompute.python import dp_mf_aggregator
from fcp.confidentialcompute.python import external_service_handle
from fcp.confidentialcompute.python import min_sep_data_source
import federated_language as flang
from federated_language.proto import computation_pb2
from federated_language.proto import data_type_pb2
import jax
import jax.numpy as jnp
from jax_privacy import noise_addition
from jax_privacy.matrix_factorization import buffered_toeplitz
import numpy as np
import tensorflow as tf
import tensorflow_federated as tff
from tensorflow_federated.proto.v0 import executor_pb2
import tree


@contextlib.contextmanager
def time_scope(name: str, metrics: dict[str, Any]):
  """Context manager that records elapsed wall-clock time into `metrics`."""
  start = time.perf_counter()
  try:
    yield
  finally:
    end = time.perf_counter()
    metrics[f'time:{name}'] = end - start


class InputReaderThread(threading.Thread):
  """A thread that reads inputs from a data source and writes to a queue."""

  def __init__(
      self,
      data_source_iterator: flang.program.FederatedDataSourceIterator,
      data_queue: queue.Queue[Any],
      cohort_size: int,
  ):
    super().__init__(
        target=self._read_inputs, name='InputReaderThread', daemon=True
    )
    self._data_source_iterator = data_source_iterator
    self._queue = data_queue
    self._cohort_size = cohort_size

  def _read_inputs(self):
    try:
      while True:
        self._queue.put(self._data_source_iterator.select(self._cohort_size))
    except Exception as e:  # pylint: disable=broad-except
      self._queue.put(e)


def load_params(
    external_handle: external_service_handle.ExternalServiceHandle,
) -> dict[str, Any]:
  """Loads program parameters from the external handle.

  All parameters must be provided via the "program_params" config id.

  Args:
    external_handle: The external service handle.

  Returns:
    A dict of parameter values read from the external handle.
  """
  params_file_path = external_handle.get_filename_for_config_id(
      'program_params'
  )
  with open(params_file_path, 'r', encoding='utf-8') as f:
    return json.load(f)


def load_model(
    external_handle: external_service_handle.ExternalServiceHandle,
    model_id: str,
) -> tff.learning.models.FunctionalModel:
  """Extracts a model zip and loads it as a TFF FunctionalModel.

  Args:
    external_handle: The external service handle.
    model_id: The config ID for the model zip file.

  Returns:
    A loaded TFF FunctionalModel.
  """
  zip_file_path = external_handle.get_filename_for_config_id(model_id)
  model_path = os.path.join(os.path.dirname(zip_file_path), model_id)
  with zipfile.ZipFile(zip_file_path, 'r') as zip_ref:
    zip_ref.extractall(model_path)
  return tff.learning.models.load_functional_model(model_path)


def create_preprocessing_comp(
    decode_fn: Callable[[tf.Tensor], Any],
    batch_size: int,
    drop_remainder: bool,
    max_batches_per_client: int,
    epochs: int,
    shuffle_buffer_size: int | None = None,
) -> flang.framework.Computation:
  """Creates a TFF computation that preprocesses client data.

  Args:
    decode_fn: A function that transforms raw example batches into the model's
      expected input format.
    batch_size: Batch size for client data.
    drop_remainder: Whether to drop the last incomplete batch.
    max_batches_per_client: Maximum number of batches per client.
    epochs: Number of epochs to repeat the dataset.
    shuffle_buffer_size: If set, shuffle the dataset with this buffer size
      before batching. Defaults to no shuffling.

  Returns:
    A TFF computation for client input preprocessing.
  """

  @tff.tensorflow.computation(tf.TensorSpec(shape=[None], dtype=tf.string))
  def _client_input_preprocessing(
      serialized_inputs: tf.Tensor,
  ) -> tf.data.Dataset:
    """Converts a tensor of serialized inputs to a tf.data.Dataset."""
    dataset = tf.data.Dataset.from_tensor_slices(serialized_inputs)
    dataset = dataset.filter(lambda x: tf.strings.length(x) > 0)
    if shuffle_buffer_size is not None:
      dataset = dataset.shuffle(buffer_size=shuffle_buffer_size)
    dataset = (
        dataset.batch(batch_size, drop_remainder=drop_remainder)
        .take(max_batches_per_client)
        .repeat(epochs)
    )
    return dataset.map(decode_fn)

  return _client_input_preprocessing


_RECOVERY_STATE_KEY = 'recovery'

_DATA_SOURCE_ITERATOR_KEY = 'data_source_iterator'

_EVAL_DATA_SOURCE_ITERATOR_KEY = 'eval_data_source_iterator'

_ROUND_INDEX_KEY = 'round_index'

_STATE_KEY = 'state'

_PARAMS_KEY = 'params'

_BLT_MIN_BUFFERS = 3

_BLT_MAX_BUFFERS = 5

SERVER_OPTIMIZER_FNS: dict[
    str, Callable[..., tff.learning.optimizers.Optimizer]
] = {
    'SGD': tff.learning.optimizers.build_sgdm,
    'SGDM': tff.learning.optimizers.build_sgdm,
    'Adam': tff.learning.optimizers.build_adam,
    'AdaGrad': tff.learning.optimizers.build_adagrad,
    'Yogi': tff.learning.optimizers.build_yogi,
}

CLIENT_OPTIMIZER_FNS: dict[
    str, Callable[..., tff.learning.optimizers.Optimizer]
] = {
    'SGD': tff.learning.optimizers.build_sgdm,
    'AdaGrad': tff.learning.optimizers.build_adagrad,
    'Adam': tff.learning.optimizers.build_adam,
}


def _serialize_blt(
    blt: buffered_toeplitz.BufferedToeplitz,
) -> dict[str, Any]:
  """Serializes BLT parameters into a dictionary with bit-exact Base64 arrays.

  Args:
    blt: The BufferedToeplitz instance to serialize.

  Returns:
    A dict containing bit-exact base64-encoded float64 bytes of `buf_decay` and
    `output_scale`, as well as human-readable float lists.
  """
  buf_decay_bytes = np.asarray(blt.buf_decay, dtype=np.float64).tobytes()
  output_scale_bytes = np.asarray(blt.output_scale, dtype=np.float64).tobytes()
  return {
      'blt_buf_decay_b64': base64.b64encode(buf_decay_bytes).decode('ascii'),
      'blt_output_scale_b64': (
          base64.b64encode(output_scale_bytes).decode('ascii')
      ),
      'blt_buf_decay': [float(x) for x in blt.buf_decay],
      'blt_output_scale': [float(x) for x in blt.output_scale],
      'blt_num_buffers': int(blt.buf_decay.shape[0]),
  }


def _deserialize_blt(
    derived_params: dict[str, Any],
) -> buffered_toeplitz.BufferedToeplitz:
  """Deserializes a BufferedToeplitz from base64-encoded arrays in derived_params.

  Args:
    derived_params: Dictionary containing 'blt_buf_decay_b64' and
      'blt_output_scale_b64'.

  Returns:
    A BufferedToeplitz object with exact float64 values restored.
  """
  buf_decay_bytes = base64.b64decode(derived_params['blt_buf_decay_b64'])
  output_scale_bytes = base64.b64decode(derived_params['blt_output_scale_b64'])
  buf_decay = np.frombuffer(buf_decay_bytes, dtype=np.float64)
  output_scale = np.frombuffer(output_scale_bytes, dtype=np.float64)
  return buffered_toeplitz.BufferedToeplitz.build(
      buf_decay=buf_decay,
      output_scale=output_scale,
      dtype=jnp.float64,
  )


def _parse_optimizer_params(params_str: str) -> dict[str, Any]:
  """Parses a string of optimizer parameters like 'beta_1:0.9,beta_2:0.999'."""
  if not params_str:
    return {}
  params_dict = {}
  for item in params_str.split(','):
    if ':' not in item:
      raise ValueError(f'Invalid optimizer param: {item}. Expected key:value.')
    key, value = item.split(':', 1)
    stripped_key = key.strip()
    if stripped_key in params_dict:
      raise ValueError(
          f'Duplicate optimizer param: {stripped_key}. Expected unique keys.'
      )
    stripped_value = value.strip()
    if stripped_value.lower() == 'true':
      params_dict[stripped_key] = True
    elif stripped_value.lower() == 'false':
      params_dict[stripped_key] = False
    else:
      try:
        params_dict[stripped_key] = float(stripped_value)
      except ValueError as exc:
        raise ValueError(
            f'Invalid value for optimizer param {stripped_key}: '
            f"'{stripped_value}'. Expected a float or boolean value."
        ) from exc
  return params_dict


def create_server_optimizer(
    params_dict: dict[str, Any],
) -> tff.learning.optimizers.Optimizer:
  """Creates server optimizer from program parameters.

  Args:
    params_dict: A dict of program parameters. Must contain
      ``server_optimizer``, ``server_learning_rate``, and optionally
      ``server_optimizer_params``.

  Returns:
    A ``tff.learning.optimizers.Optimizer``.
  """
  optimizer_fn = SERVER_OPTIMIZER_FNS.get(params_dict['server_optimizer'])
  if not optimizer_fn:
    raise NotImplementedError(
        f"Setting --server_optimizer to {params_dict['server_optimizer']} is"
        ' not yet supported when using TFF-based Brella.'
    )
  arg_dict = {'learning_rate': float(params_dict['server_learning_rate'])}
  arg_dict.update(
      _parse_optimizer_params(params_dict.get('server_optimizer_params', ''))
  )
  return optimizer_fn(**arg_dict)


def create_client_optimizer(
    params_dict: dict[str, Any],
) -> tff.learning.optimizers.Optimizer:
  """Creates client optimizer from program parameters.

  Args:
    params_dict: A dict of program parameters. Must contain
      ``client_optimizer``, ``client_learning_rate``, and optionally
      ``client_optimizer_params``.

  Returns:
    A ``tff.learning.optimizers.Optimizer``.
  """
  optimizer_fn = CLIENT_OPTIMIZER_FNS.get(params_dict['client_optimizer'])
  if not optimizer_fn:
    raise NotImplementedError(
        f"Setting --client_optimizer to {params_dict['client_optimizer']} is"
        ' not yet supported when using TFF-based Brella.'
    )
  arg_dict = {'learning_rate': float(params_dict['client_learning_rate'])}
  arg_dict.update(
      _parse_optimizer_params(params_dict.get('client_optimizer_params', ''))
  )
  return optimizer_fn(**arg_dict)


def get_model_aggregator(
    model: tff.learning.models.FunctionalModel,
    params_dict: dict[str, Any],
    blt: buffered_toeplitz.BufferedToeplitz | None = None,
) -> tff.aggregators.WeightedAggregationFactory:
  """Returns the tree-aggregation DPFTRL aggregator."""
  noise_multiplier = float(params_dict['noise_multiplier'])
  clip_norm = float(params_dict['clip_norm'])
  zeroing_multiplier = float(params_dict['zeroing_multiplier'])

  if params_dict['use_matrix_factorization']:
    if params_dict['use_adaptive_clipping']:
      raise ValueError(
          'Adaptive clipping is not supported with matrix factorization.'
      )
    if blt is None:
      raise ValueError('blt must be provided when using matrix factorization.')
    matrix_mechanism = blt.inverse_as_streaming_matrix()
    global_noise_seed = tf.cast(tf.timestamp() * 1e6, tf.int64).numpy()
    privatizer = noise_addition.matrix_factorization_privatizer(
        matrix_mechanism,
        stddev=noise_multiplier * clip_norm,
        prng_key=jax.random.PRNGKey(global_noise_seed),
        dtype=jnp.float32,
    )
    dp_aggregator = dp_mf_aggregator.DPMFAggregatorFactory(
        gradient_privatizer=privatizer,
        clients_per_round=params_dict['cohort_size'],
        l2_clip_norm=clip_norm,
    )
  else:
    trainable_weights, _ = model.initial_weights
    record_specs = tree.map_structure(
        lambda arr: flang.TensorType(dtype=arr.dtype, shape=arr.shape),
        trainable_weights,
    )
    if params_dict['use_adaptive_clipping']:
      dp_aggregator = (
          tff.aggregators.DifferentiallyPrivateFactory.tree_adaptive(
              noise_multiplier=noise_multiplier,
              clients_per_round=params_dict['cohort_size'],
              record_specs=record_specs,
              initial_l2_norm_clip=clip_norm,
          )
      )
    else:
      dp_aggregator = (
          tff.aggregators.DifferentiallyPrivateFactory.tree_aggregation(
              noise_multiplier=noise_multiplier,
              clients_per_round=params_dict['cohort_size'],
              l2_norm_clip=clip_norm,
              record_specs=record_specs,
              noise_seed=None,
              use_efficient=True,
          )
      )
  dp_aggregator_with_zeroing = tff.aggregators.zeroing_factory(
      zeroing_multiplier * clip_norm,
      dp_aggregator,
  )
  return tff.aggregators.as_weighted_aggregator(
      tff.learning.add_debug_measurements(dp_aggregator_with_zeroing)
  )


def _build_min_mean_max_aggregator(
    metric_finalizers: (
        tff.learning.metrics.MetricFinalizersType
        | tff.learning.metrics.FunctionalMetricFinalizersType
    ),
    unfinalized_metrics_type: flang.StructWithPythonType | None,
) -> tff.learning.metrics.MetricsAggregatorType:
  """Creates an aggregator that returns the min, mean, and max of metrics."""

  def _finalize_then_min_mean_max(unfinalized_metrics):

    if callable(metric_finalizers):

      def finalize_fn(unfinalized_metrics):
        finalized_metrics = metric_finalizers(unfinalized_metrics)
        return tf.nest.map_structure(
            lambda x: tf.cast(x, tf.float32), finalized_metrics
        )

    else:

      def finalize_fn(unfinalized_metrics):
        finalized_metrics = {}
        for metric_name, metric_finalizer in metric_finalizers.items():
          finalized_metrics[metric_name] = tf.cast(
              metric_finalizer(unfinalized_metrics[metric_name]),
              tf.float32,
          )
        return finalized_metrics

    if unfinalized_metrics_type is not None:
      finalize_comp = tff.tensorflow.computation(
          finalize_fn, unfinalized_metrics_type
      )
    else:
      finalize_comp = tff.tensorflow.computation(finalize_fn)

    finalized_metrics = flang.federated_map(finalize_comp, unfinalized_metrics)
    return flang.federated_zip({
        'min': flang.federated_min(finalized_metrics),
        'mean': flang.federated_mean(finalized_metrics),
        'max': flang.federated_max(finalized_metrics),
    })

  if unfinalized_metrics_type is not None:
    return flang.federated_computation(
        _finalize_then_min_mean_max,
        flang.FederatedType(unfinalized_metrics_type, flang.CLIENTS),
    )
  else:
    return flang.federated_computation(_finalize_then_min_mean_max)


def build_client_distribution_aggregator() -> (
    tff.learning.metrics.MetricsAggregatorType
):
  """Creates an aggregator that aggregates the bounds of client metrics.

  This concatenates the default ``sum_then_finalize`` aggregator (a population
  level per-example metric) with a custom aggregator that returns the min, mean,
  and max of per-client finalized metrics.

  Returns:
    A callable metrics aggregator matching TFF's aggregator signature.
  """

  def sum_min_mean_max_aggregator(
      metric_finalizers: (
          tff.learning.metrics.MetricFinalizersType
          | tff.learning.metrics.FunctionalMetricFinalizersType
      ),
      local_unfinalized_metrics_type: flang.StructWithPythonType | None = None,
  ) -> flang.framework.Computation:
    sum_then_finalize_comp = tff.learning.metrics.sum_then_finalize(
        metric_finalizers, local_unfinalized_metrics_type
    )
    min_mean_max_comp = _build_min_mean_max_aggregator(
        metric_finalizers, local_unfinalized_metrics_type
    )

    def aggregator_computation(client_local_unfinalized_metrics):
      summed = sum_then_finalize_comp(client_local_unfinalized_metrics)
      distribution = min_mean_max_comp(client_local_unfinalized_metrics)

      @tff.tensorflow.computation
      def _zip_metrics(summed_metrics, distribution_metrics):
        zipped: dict[str, Any] = {}
        for key, value in summed_metrics.items():
          zipped[key] = value
          for suffix in ['min', 'mean', 'max']:
            zipped[f'{key}/{suffix}'] = distribution_metrics[suffix][key]
        return zipped

      metrics = flang.federated_map(_zip_metrics, (summed, distribution))

      def _is_scalar_or_single_value_array(type_spec: flang.Type) -> bool:
        if not isinstance(type_spec, flang.TensorType):
          return True
        else:
          is_scalar_or_single_value = not type_spec.shape or all(
              dim == 1 for dim in type_spec.shape
          )
          if not is_scalar_or_single_value:
            logging.warning('Not scalar or single value: %r', type_spec)
          return is_scalar_or_single_value

      if not flang.framework.type_contains_only(
          metrics.type_signature.member, _is_scalar_or_single_value_array
      ):
        raise ValueError(
            'Metrics must be scalar or single value arrays. Found:'
            f' {metrics.type_signature}'
        )
      return metrics

    if local_unfinalized_metrics_type is not None:
      return flang.federated_computation(
          aggregator_computation,
          flang.FederatedType(local_unfinalized_metrics_type, flang.CLIENTS),
      )
    else:
      return flang.federated_computation(aggregator_computation)

  return sum_min_mean_max_aggregator


def _build_training_and_eval_processes(
    model: tff.learning.models.FunctionalModel,
    params_dict: dict[str, Any],
    decode_fn: Any,
    blt: buffered_toeplitz.BufferedToeplitz,
) -> tuple[Any, Any]:
  """Builds training and evaluation TFF processes.

  Args:
    model: The functional model to train.
    params_dict: Combined program parameters (provided + derived).
    decode_fn: Function that decodes raw examples into model input format.
    blt: The optimized BLT matrix for matrix factorization.

  Returns:
    A ``(training_process, evaluation_process)`` tuple, both composed with
    the client preprocessing computation.
  """
  client_weighting_raw = params_dict['client_weighting']
  if client_weighting_raw == 'uniform':
    client_weighting = tff.learning.ClientWeighting.UNIFORM
  elif client_weighting_raw == 'num_examples':
    client_weighting = tff.learning.ClientWeighting.NUM_EXAMPLES
  else:
    raise ValueError(
        f'Unsupported client weighting: {client_weighting_raw!r}, supported'
        " values: ['uniform', 'num_examples']."
    )
  training_process = tff.learning.algorithms.build_weighted_fed_avg(
      model_fn=model,
      client_optimizer_fn=create_client_optimizer(params_dict),
      server_optimizer_fn=create_server_optimizer(params_dict),
      client_weighting=client_weighting,
      model_aggregator=get_model_aggregator(
          model,
          params_dict,
          blt,
      ),
      metrics_aggregator=build_client_distribution_aggregator(),
      measure_timing=True,
  )
  preprocessing = create_preprocessing_comp(
      decode_fn=decode_fn,
      batch_size=params_dict['batch_size'],
      drop_remainder=params_dict['drop_remainder'],
      max_batches_per_client=params_dict['max_batches_per_client'],
      epochs=params_dict['epochs'],
  )
  training_process = (
      tff.simulation.compose_dataset_computation_with_learning_process(
          preprocessing, training_process
      )
  )
  evaluation_process = tff.learning.algorithms.build_fed_eval(model_fn=model)
  evaluation_process = (
      tff.simulation.compose_dataset_computation_with_learning_process(
          preprocessing, evaluation_process
      )
  )
  return training_process, evaluation_process


def _initialize_fresh_params(
    external_handle: external_service_handle.ExternalServiceHandle,
    max_zcdp: float,
    timing_metrics: dict[str, float],
) -> tuple[dict[str, Any], Any, list[tuple[Any, str]]]:
  """Loads params, derives privacy parameters, and builds release candidates.

  This is called for fresh (non-recovery) training runs. It reads program
  parameters from the external handle, optimizes the BLT, derives noise/zcdp
  parameters, and prepares the provided_params and derived_params releases.

  Args:
    external_handle: The external service handle.
    max_zcdp: Maximum approved zCDP value for this program.
    timing_metrics: Dictionary for timing metrics.

  Returns:
    A tuple of (params_dict, blt, additional_release_candidates).
  """
  provided_params = load_params(external_handle)

  max_possible_min_sep = math.floor(
      len(external_handle.blob_ids) / provided_params['cohort_size']
  )
  with time_scope('blt.optimize', timing_metrics):
    blt = buffered_toeplitz.optimize(
        n=provided_params['num_rounds'],
        min_sep=max_possible_min_sep,
        max_participations=None,
        min_buffers=_BLT_MIN_BUFFERS,
        max_buffers=_BLT_MAX_BUFFERS,
    )

  has_noise_multiplier = (
      'noise_multiplier' in provided_params
      and provided_params['noise_multiplier'] is not None
  )
  has_target_zcdp = (
      'target_zcdp' in provided_params
      and provided_params['target_zcdp'] is not None
  )

  if has_noise_multiplier and has_target_zcdp:
    raise ValueError(
        "Cannot specify both 'noise_multiplier' and 'target_zcdp' in"
        ' program_params.'
    )

  derived_params = {
      'blob_id_count': len(external_handle.blob_ids),
      'max_min_separation': max_possible_min_sep,
      'max_zcdp': max_zcdp,
      'blt_min_buffers': _BLT_MIN_BUFFERS,
      'blt_max_buffers': _BLT_MAX_BUFFERS,
      **_serialize_blt(blt),
  }

  use_matrix_factorization = bool(
      provided_params.get('use_matrix_factorization', True)
  )

  if has_target_zcdp or not has_noise_multiplier:
    target_zcdp = (
        float(provided_params['target_zcdp']) if has_target_zcdp else max_zcdp
    )
    if target_zcdp > max_zcdp:
      raise ValueError(
          f'Target zCDP: {target_zcdp} is greater than max_zcdp: {max_zcdp}.'
      )
    if use_matrix_factorization:
      noise_multiplier = accounting.noise_multiplier_for_blt(
          blt,
          provided_params['num_rounds'],
          target_zcdp,
          max_possible_min_sep,
      )
    else:
      noise_multiplier = accounting.min_sep_data_source_noise_multiplier(
          target_zcdp,
          provided_params['num_rounds'],
          max_possible_min_sep,
      )
    print(
        f'Running with target_zcdp: {target_zcdp}, derived noise_multiplier:'
        f" {noise_multiplier}, total_steps: {provided_params['num_rounds']},"
        f' min_sep: {max_possible_min_sep}, use_matrix_factorization:'
        f' {use_matrix_factorization}.'
    )
    zcdp = float(target_zcdp)
    derived_params['noise_multiplier'] = noise_multiplier
    derived_params['zcdp'] = zcdp
  else:
    noise_multiplier = float(provided_params['noise_multiplier'])
    if use_matrix_factorization:
      zcdp = float(
          accounting.zcdp_for_blt(
              blt,
              provided_params['num_rounds'],
              noise_multiplier,
              max_possible_min_sep,
          )
      )
    else:
      zcdp = float(
          accounting.min_sep_data_source_zcdp(
              noise_multiplier,
              provided_params['num_rounds'],
              max_possible_min_sep,
          )
      )
    if zcdp > max_zcdp:
      raise ValueError(
          f'Current zCDP: {zcdp} is greater than max_zcdp: {max_zcdp}.'
          ' Training parameters'
          f' (noise_multiplier={noise_multiplier},'
          f" total_steps={provided_params['num_rounds']},"
          f' min_sep={max_possible_min_sep}, use_matrix_factorization='
          f'{use_matrix_factorization}) result in a zCDP that exceeds'
          ' the approved privacy guarantee.'
      )
    print(
        f'Running with zCDP: {zcdp}, with noise_multiplier:'
        f" {noise_multiplier}, total_steps: {provided_params['num_rounds']},"
        f' min_sep: {max_possible_min_sep}, use_matrix_factorization:'
        f' {use_matrix_factorization}.'
    )
    derived_params['zcdp'] = zcdp

  # Release provided and derived params separately in round 1 so there is
  # a complete auditable record of what was provided vs computed.
  additional_release_candidates = [
      (json.dumps(provided_params), 'provided_params'),
      (json.dumps(derived_params), 'derived_params'),
  ]

  params_dict = {**provided_params, **derived_params}
  return params_dict, blt, additional_release_candidates


def _run_training_loop(
    training_process: Any,
    evaluation_process: Any,
    params_dict: dict[str, Any],
    external_handle: external_service_handle.ExternalServiceHandle,
    timing_metrics: dict[str, float],
    recovered_state: Any | None,
    additional_release_candidates: list[tuple[Any, str]],
) -> None:
  """Initializes or recovers state, then runs the training loop.

  Args:
    training_process: The composed TFF training process.
    evaluation_process: The composed TFF evaluation process.
    params_dict: Combined program parameters.
    external_handle: Handle for saving recovery info and releases.
    timing_metrics: Dictionary for timing metrics.
    recovered_state: Deserialized recovery state if recovering, or None.
    additional_release_candidates: Extra release candidates to include in round
      1 (e.g., provided_params and derived_params JSON releases).
  """
  num_eval_rounds_per_checkpoint = params_dict['num_eval_rounds_per_checkpoint']

  # Initialize or recover training state.
  if recovered_state is not None:
    data_source_iterator = min_sep_data_source.MinSepDataSourceIterator.restore(
        recovered_state[_DATA_SOURCE_ITERATOR_KEY], external_handle
    )
    eval_data_source_iterator = (
        min_sep_data_source.MinSepDataSourceIterator.restore(
            recovered_state[_EVAL_DATA_SOURCE_ITERATOR_KEY],
            external_handle,
        )
    )
    initial_round_id = recovered_state[_ROUND_INDEX_KEY]
    state = recovered_state[_STATE_KEY]
  else:
    train_data_source = min_sep_data_source.MinSepDataSource(
        params_dict['max_min_separation'],
        external_handle,
        computation_pb2.Type(
            tensor=computation_pb2.TensorType(
                dtype=data_type_pb2.DataType.DT_STRING, dims=[-1]
            )
        ),
    )
    eval_data_source = min_sep_data_source.MinSepDataSource(
        num_eval_rounds_per_checkpoint,
        external_handle,
        computation_pb2.Type(
            tensor=computation_pb2.TensorType(
                dtype=data_type_pb2.DataType.DT_STRING, dims=[-1]
            )
        ),
    )
    data_source_iterator = train_data_source.iterator()
    eval_data_source_iterator = eval_data_source.iterator()
    initial_round_id = 0
    state = training_process.initialize()

  # Start background data prefetch threads. Limit the queue sizes to 1 to limit
  # how much memory the queue uses. We only need to prefetch one round's worth
  # of client data at a time.
  train_data_queue = queue.Queue(maxsize=1)
  InputReaderThread(
      data_source_iterator,
      train_data_queue,
      params_dict['cohort_size'],
  ).start()
  eval_data_queue = queue.Queue(maxsize=1)
  InputReaderThread(
      eval_data_source_iterator,
      eval_data_queue,
      params_dict['eval_cohort_size'],
  ).start()

  output_executor = concurrent.futures.ThreadPoolExecutor(max_workers=1)
  output_futures = []

  def _save_release(save_state, save_state_key, unencrypted_release_candidates):
    save_state_val, _ = tff.framework.serialize_value(
        save_state, flang.framework.infer_type(save_state)
    )
    unencrypted_releases = []
    for (
        unencrypted_release,
        unencrypted_release_key,
    ) in unencrypted_release_candidates:
      if isinstance(unencrypted_release, str):
        unencrypted_release_bytes = unencrypted_release.encode('utf-8')
      elif isinstance(unencrypted_release, bytes):
        unencrypted_release_bytes = unencrypted_release
      else:
        unencrypted_release_val, _ = tff.framework.serialize_value(
            unencrypted_release, flang.framework.infer_type(unencrypted_release)
        )
        unencrypted_release_bytes = unencrypted_release_val.SerializeToString()
      unencrypted_releases.append((
          unencrypted_release_bytes,
          unencrypted_release_key,
      ))
    external_handle.save_recovery_info(
        save_state_val.SerializeToString(),
        save_state_key,
        unencrypted_releases,
    )

  # Release candidates are the (value, key) pairs that will be released as
  # unencrypted information as part of the next call to _save_release to save
  # recovery information.
  release_candidates = list(additional_release_candidates)

  for num_round in range(initial_round_id + 1, params_dict['num_rounds'] + 1):
    # Asynchronously save outputs to hide I/O latency, but verify task results
    # at the start of every round. If any background write task fails (e.g.,
    # due to an aborted output connection or disk failure), calling .result()
    # immediately re-raises the exception on the main thread so the process
    # crashes as early as possible instead of completing all training rounds.
    pending_futures = []
    for future in output_futures:
      if future.done():
        future.result()
      else:
        pending_futures.append(future)
    output_futures = pending_futures

    with time_scope('client_data.get', timing_metrics):
      client_data = train_data_queue.get()
      if isinstance(client_data, Exception):
        raise client_data

    with time_scope('train.next', timing_metrics):
      state, train_metrics = training_process.next(state, client_data)

    if num_round % params_dict['eval_periodicity'] == 0:
      # Release the checkpoint if it will be evaluated. This allows the user
      # to choose the best checkpoint based on the evaluation metrics.
      release_candidates.append(
          (state.global_model_weights, f'checkpoint_round_{num_round}')
      )
      with time_scope('eval', timing_metrics):
        eval_state = evaluation_process.initialize()
        eval_state = evaluation_process.set_model_weights(
            eval_state, state.global_model_weights
        )
        for eval_round in range(num_eval_rounds_per_checkpoint):
          eval_client_data = eval_data_queue.get()
          if isinstance(eval_client_data, Exception):
            raise eval_client_data
          eval_state, eval_metrics = evaluation_process.next(
              eval_state, eval_client_data
          )
          if num_eval_rounds_per_checkpoint == 1:
            release_key = f'eval_metrics_round_{num_round}'
          else:
            release_key = f'eval_metrics_round_{num_round}_eval_{eval_round}'
          release_candidates.append((eval_metrics, release_key))

    release_metrics = {**train_metrics, **timing_metrics}
    timing_metrics.clear()
    release_candidates.insert(
        0, (release_metrics, f'metrics_round_{num_round}')
    )

    # Save recovery information before moving on to the next round. This will
    # allow the program to restart from the beginning of the next round if a
    # crash occurs before the next round completes. This operation also releases
    # any unencrypted outputs that were generated in this round (this always
    # includes training metrics and potentially also includes a checkpoint and
    # eval metrics if the eval branch was executed this round).
    save_state = {
        _DATA_SOURCE_ITERATOR_KEY: data_source_iterator.save(),
        _EVAL_DATA_SOURCE_ITERATOR_KEY: eval_data_source_iterator.save(),
        _ROUND_INDEX_KEY: num_round,
        _STATE_KEY: state,
        _PARAMS_KEY: json.dumps(params_dict),
    }
    output_futures.append(
        output_executor.submit(
            _save_release,
            save_state,
            _RECOVERY_STATE_KEY,
            list(release_candidates),
        )
    )
    release_candidates.clear()

  # Wait for all output futures to finish, re-raising any exceptions.
  for future in output_futures:
    future.result()
  output_executor.shutdown()


def run_training(
    external_handle: external_service_handle.ExternalServiceHandle,
    decode_fn: Any,
    *,
    max_zcdp: float,
) -> None:
  """Runs a complete federated training and eval job.

  Args:
    external_handle: The external service handle.
    decode_fn: A function that transforms raw example batches into the model's
      expected input format.
    max_zcdp: Maximum approved zCDP value for this program.
  """
  # Required by jnp.float64.
  jax.config.update('jax_enable_x64', True)
  # Set the serialization version to be compatible with the version of TF used
  # in the TEE binary.
  jax.config.update('jax_serialization_version', 8)

  timing_metrics = dict[str, float]()
  additional_release_candidates = []
  recovered_state = None

  recovered_state_val = external_handle.restore_recovery_info(
      _RECOVERY_STATE_KEY
  )
  if recovered_state_val is not None:
    recovered_state, _ = tff.framework.deserialize_value(
        executor_pb2.Value.FromString(recovered_state_val)
    )
    params_dict = json.loads(recovered_state[_PARAMS_KEY])
    blt = _deserialize_blt(params_dict)
  else:
    params_dict, blt, additional_release_candidates = _initialize_fresh_params(
        external_handle, max_zcdp, timing_metrics
    )

  model = load_model(external_handle, str(params_dict['model_id']))

  training_process, evaluation_process = _build_training_and_eval_processes(
      model,
      params_dict,
      decode_fn,
      blt,
  )

  if params_dict['num_eval_rounds_per_checkpoint'] < 1:
    raise ValueError('Number of eval rounds per checkpoint must be at least 1.')

  _run_training_loop(
      training_process,
      evaluation_process,
      params_dict,
      external_handle,
      timing_metrics,
      recovered_state=recovered_state,
      additional_release_candidates=additional_release_candidates,
  )


_MAX_ZCDP = 2.63

_FEATURE_NAMES = (
    'is_completion_type',
    'literal_candidate_ngram_count_in_user_history',
    'top_candidate_ngram_count_in_user_history',
    'literal_main_lm_score',
    'middle_main_lm_score',
    'literal_candidate_text_length',
    'top_candidate_text_length',
    'literal_candidate_distance_mean',
    'literal_candidate_distance_stddev',
    'top_candidate_distance_mean',
    'top_candidate_distance_stddev',
    'literal_candidate_is_in_user_history',
    'top_candidate_is_in_user_history',
    'omission_num_v2',
    'insertion_num_v2',
    'transposition_num_v2',
    'nearby_substitution_num_v2',
    'general_substitution_num_v2',
    'edit_distance_v2',
    'most_common_key_width',
    'most_common_key_height',
    'literal_candidate_oov_num',
    'top_candidate_oov_num',
    'is_case_correction',
    'touch_points_distance_mean',
    'touch_points_distance_stddev',
    'literal_candidate_char_num',
    'top_candidate_char_num',
    'literal_user_history_lm_score',
    'middle_user_history_lm_score',
    'touch_points_distance_min',
    'touch_points_distance_max',
    'touch_points_distance_sum',
    'touch_points_x_distance_min',
    'touch_points_x_distance_max',
    'touch_points_x_distance_sum',
    'touch_points_x_distance_mean',
    'touch_points_x_distance_stddev',
    'touch_points_y_distance_min',
    'touch_points_y_distance_max',
    'touch_points_y_distance_sum',
    'touch_points_y_distance_mean',
    'touch_points_y_distance_stddev',
    'touch_points_x_max',
    'touch_points_x_mean',
    'touch_points_x_min',
    'touch_points_x_stddev',
    'touch_points_x_sum',
    'touch_points_y_max',
    'touch_points_y_mean',
    'touch_points_y_min',
    'touch_points_y_stddev',
    'touch_points_y_sum',
    'touch_points_distr',
    'touch_points_x_distr',
    'touch_points_y_distr',
    'touch_points_ndistr',
    'touch_points_x_ndistr',
    'touch_points_y_ndistr',
    'l_vowel_n',
    'l_vowel_r',
    't_vowel_n',
    't_vowel_r',
    'vowel_d',
    'vowel_p',
    'vowel_r',
    'vowel_s',
    'bos',
    'mlm_score_d',
    'mlm_score_p',
    'mlm_score_r',
    'mlm_score_s',
    'uhlm_score_d',
    'uhlm_score_p',
    'uhlm_score_r',
    'uhlm_score_s',
    'uh_ngram_c_d',
    'uh_ngram_c_p',
    'uh_ngram_c_r',
    'uh_ngram_c_s',
    'text_len_d',
    'text_len_p',
    'text_len_r',
    'text_len_s',
    'key_wh_r',
    'dist_mean_d',
    'dist_mean_p',
    'dist_mean_r',
    'dist_mean_s',
    'dist_stddev_d',
    'dist_stddev_p',
    'dist_stddev_r',
    'dist_stddev_s',
    'c_dist_mean_d',
    'c_dist_mean_p',
    'c_dist_mean_r',
    'c_dist_mean_s',
    'c_dist_stddev_d',
    'c_dist_stddev_p',
    'c_dist_stddev_r',
    'c_dist_stddev_s',
    'l_dist_max',
    'l_dist_mean',
    'l_dist_min',
    'l_dist_stddev',
    't_dist_max',
    't_dist_mean',
    't_dist_min',
    't_dist_stddev',
    'domain_oh',
    'literal_candidate_base_chars',
    'top_candidate_base_chars',
    'top_candidate_type',
    'touch_points_x_coord',
    'touch_points_y_coord',
    'literal_candidate_x_coord',
    'literal_candidate_y_coord',
    'top_candidate_x_coord',
    'top_candidate_y_coord',
)

_ES_MX_FEATURE_NAMES = (
    'is_completion_type',
    'literal_candidate_ngram_count_in_user_history',
    'top_candidate_ngram_count_in_user_history',
    'literal_main_lm_score',
    'middle_main_lm_score',
    'literal_candidate_text_length',
    'top_candidate_text_length',
    'literal_candidate_rescored_sm_score',
    'top_candidate_rescored_sm_score',
    'literal_candidate_distance_mean',
    'literal_candidate_distance_stddev',
    'top_candidate_distance_mean',
    'top_candidate_distance_stddev',
    'literal_candidate_is_in_user_history',
    'top_candidate_is_in_user_history',
    'omission_num_v2',
    'insertion_num_v2',
    'transposition_num_v2',
    'nearby_substitution_num_v2',
    'general_substitution_num_v2',
    'edit_distance_v2',
    'most_common_key_width',
    'most_common_key_height',
    'literal_candidate_oov_num',
    'top_candidate_oov_num',
    'is_case_correction',
    'touch_points_distance_mean',
    'touch_points_distance_stddev',
    'literal_candidate_char_num',
    'top_candidate_char_num',
    'literal_user_history_lm_score',
    'middle_user_history_lm_score',
    'touch_points_distance_min',
    'touch_points_distance_max',
    'touch_points_distance_sum',
    'touch_points_x_distance_min',
    'touch_points_x_distance_max',
    'touch_points_x_distance_sum',
    'touch_points_x_distance_mean',
    'touch_points_x_distance_stddev',
    'touch_points_y_distance_min',
    'touch_points_y_distance_max',
    'touch_points_y_distance_sum',
    'touch_points_y_distance_mean',
    'touch_points_y_distance_stddev',
    'touch_points_x_max',
    'touch_points_x_mean',
    'touch_points_x_min',
    'touch_points_x_stddev',
    'touch_points_x_sum',
    'touch_points_y_max',
    'touch_points_y_mean',
    'touch_points_y_min',
    'touch_points_y_stddev',
    'touch_points_y_sum',
    'touch_points_distr',
    'touch_points_x_distr',
    'touch_points_y_distr',
    'touch_points_ndistr',
    'touch_points_x_ndistr',
    'touch_points_y_ndistr',
    'l_vowel_n',
    'l_vowel_r',
    't_vowel_n',
    't_vowel_r',
    'vowel_d',
    'vowel_p',
    'vowel_r',
    'vowel_s',
    'bos',
    'mlm_score_d',
    'mlm_score_p',
    'mlm_score_r',
    'mlm_score_s',
    'uhlm_score_d',
    'uhlm_score_p',
    'uhlm_score_r',
    'uhlm_score_s',
    'uh_ngram_c_d',
    'uh_ngram_c_p',
    'uh_ngram_c_r',
    'uh_ngram_c_s',
    'text_len_d',
    'text_len_p',
    'text_len_r',
    'text_len_s',
    'key_wh_r',
    'dist_mean_d',
    'dist_mean_p',
    'dist_mean_r',
    'dist_mean_s',
    'dist_stddev_d',
    'dist_stddev_p',
    'dist_stddev_r',
    'dist_stddev_s',
    'c_dist_mean_d',
    'c_dist_mean_p',
    'c_dist_mean_r',
    'c_dist_mean_s',
    'c_dist_stddev_d',
    'c_dist_stddev_p',
    'c_dist_stddev_r',
    'c_dist_stddev_s',
    'l_dist_max',
    'l_dist_mean',
    'l_dist_min',
    'l_dist_stddev',
    't_dist_max',
    't_dist_mean',
    't_dist_min',
    't_dist_stddev',
    'domain_oh',
    'literal_candidate_base_chars',
    'top_candidate_base_chars',
    'top_candidate_type',
)

_LABEL_NAMES = (
    'label',
    'y_pred_baseline',
    'literal_is_final',
    'top_is_final',
    'top_candidate_type',
    'literal_candidate_oov_num',
    'omission_num_v2',
)


_INT64_NAMES = frozenset({
    'label',
    'provided_auto_correction',
    'last_example_on_branch',
    'revision_num',
    'submission_type',
    'deletion_action_num',
})


_COORD_NAMES = frozenset({
    'touch_points_x_coord',
    'touch_points_y_coord',
    'literal_candidate_x_coord',
    'literal_candidate_y_coord',
    'top_candidate_x_coord',
    'top_candidate_y_coord',
})


_FEATURE_DIMS = {
    'literal_candidate_char_num': 3,
    'top_candidate_char_num': 3,
    'touch_points_distr': 4,
    'touch_points_x_distr': 2,
    'touch_points_y_distr': 2,
    'touch_points_ndistr': 4,
    'touch_points_x_ndistr': 2,
    'touch_points_y_ndistr': 2,
    'domain_oh': 15,
    'literal_candidate_base_chars': 20,
    'top_candidate_base_chars': 20,
    'touch_points_x_coord': 20,
    'touch_points_y_coord': 20,
    'literal_candidate_x_coord': 20,
    'literal_candidate_y_coord': 20,
    'top_candidate_x_coord': 20,
    'top_candidate_y_coord': 20,
}


def _resize_to_dim(d: tf.Tensor, target_dim: int, def_val: Any) -> tf.Tensor:
  """Resizes a tensor's second dimension to target_dim by padding or slicing."""
  cur_cols = tf.shape(d)[1]
  return tf.cond(
      cur_cols < target_dim,
      lambda: tf.pad(
          d,
          [[0, 0], [0, target_dim - cur_cols]],
          constant_values=tf.cast(def_val, d.dtype),
      ),
      lambda: d[:, :target_dim],
  )


def create_decode_fn(
    inputs_def_wrapper: Any = None,
    support_two_labels: bool = True,
    feature_names: Sequence[str] = _FEATURE_NAMES,
    label_names: Sequence[str] = _LABEL_NAMES,
    x_dim: int | None = None,
    y_dim: int | None = None,
) -> Any:
  """Creates a decode_example function tailored to the ACT feature schema."""
  if inputs_def_wrapper is not None:
    feature_names = inputs_def_wrapper.feature_names
    label_names = inputs_def_wrapper.label_names
    x_dim = inputs_def_wrapper.x_dim
    y_dim = inputs_def_wrapper.y_dim
  if x_dim is None:
    x_dim = sum(_FEATURE_DIMS.get(name, 1) for name in feature_names)
  if y_dim is None:
    y_dim = len(label_names)

  all_names = list(feature_names) + list(label_names)

  feature_specs = {}
  for name in all_names:
    if name in _INT64_NAMES:
      feature_specs[name] = tf.io.VarLenFeature(tf.int64)
    else:
      feature_specs[name] = tf.io.VarLenFeature(tf.float32)

  def decode_example(examples: tf.Tensor) -> dict[str, Any]:
    parsed = tf.io.parse_example(examples, features=feature_specs)

    x_list = []
    for name in feature_names:
      if name in _INT64_NAMES:
        default_val = 0
      elif name in _COORD_NAMES:
        default_val = -2.0
      else:
        default_val = 0.0
      dense = tf.sparse.to_dense(parsed[name], default_value=default_val)
      dense = tf.reshape(dense, [tf.shape(examples)[0], -1])
      dim = _FEATURE_DIMS.get(name, 1)
      dense = _resize_to_dim(dense, dim, default_val)
      x_list.append(tf.cast(dense, tf.float32))
    x = tf.concat(x_list, axis=1)
    x = tf.ensure_shape(x, [None, x_dim])

    y_list = []
    for name in label_names:
      default_val = 0 if name in _INT64_NAMES else 0.0
      dense = tf.sparse.to_dense(parsed[name], default_value=default_val)
      dense = tf.reshape(dense, [tf.shape(examples)[0], -1])
      dense = _resize_to_dim(dense, 1, default_val)
      y_list.append(tf.cast(dense, tf.float32))
    y = tf.concat(y_list, axis=1)
    y = tf.ensure_shape(y, [None, y_dim])

    if support_two_labels:
      return {'x': x, 'y': (y, y)}
    return {'x': x, 'y': y}

  return decode_example


def trusted_program(
    external_handle: external_service_handle.ExternalServiceHandle,
) -> None:
  """Executes the ACT training loop inside the TEE."""
  params = load_params(external_handle)
  if params.get('model_id') == 'es_mx':
    decode_example = create_decode_fn(
        feature_names=_ES_MX_FEATURE_NAMES,
    )
  else:
    decode_example = create_decode_fn()
  run_training(external_handle, decode_example, max_zcdp=_MAX_ZCDP)
