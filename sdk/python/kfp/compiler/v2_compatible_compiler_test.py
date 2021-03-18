# Copyright 2021 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
"""Tests for v2-compatible compiled pipelines."""

import os
import tempfile
from typing import Callable
import unittest
import yaml

from kfp import compiler, components, dsl
from kfp.components import InputPath, OutputPath


def preprocess(uri: str, some_int: int, output_parameter_one: OutputPath(int),
               output_dataset_one: OutputPath('Dataset')):
  '''Dummy Preprocess Step.'''
  with open(output_dataset_one, 'w') as f:
    f.write('Output dataset')
  with open(output_parameter_one, 'w') as f:
    f.write("{}".format(1234))


def train(dataset: InputPath('Dataset'),
          model: OutputPath('Model'),
          num_steps: int = 100):
  '''Dummy Training Step.'''

  with open(dataset, 'r') as input_file:
    input_string = input_file.read()
    with open(model, 'w') as output_file:
      for i in range(num_steps):
        output_file.write("Step {}\n{}\n=====\n".format(i, input_string))


preprocess_op = components.create_component_from_func(preprocess,
                                                      base_image='python:3.9')
train_op = components.create_component_from_func(train)


class TestV2CompatibleModeCompiler(unittest.TestCase):

  def setUp(self) -> None:
    self._compiler = compiler.Compiler(
        mode=dsl.PipelineExecutionMode.V2_COMPATIBLE)

  def _assert_compiled_pipeline_equals_golden(self, pipeline_func: Callable,
                                              golden_yaml_filename: str):
    compiled_file = os.path.join(tempfile.mkdtemp(), 'workflow.yaml')
    self._compiler.compile(pipeline_func, package_path=compiled_file)

    test_data_dir = os.path.join(os.path.dirname(__file__), 'testdata')
    golden_file = os.path.join(test_data_dir, golden_yaml_filename)
    # Uncomment the following to update goldens.
    # TODO: place this behind some --update_goldens flag.
    # self._compiler.compile(pipeline_func, package_path=golden_file)

    with open(golden_file, 'r') as f:
      golden = yaml.safe_load(f)

    with open(compiled_file, 'r') as f:
      compiled = yaml.safe_load(f)

    for workflow in golden, compiled:
      del workflow['metadata']
      for template in workflow['spec']['templates']:
        template.pop('metadata', None)

    self.maxDiff = None
    self.assertDictEqual(golden, compiled)

  def test_two_step_pipeline(self):

    @dsl.pipeline(pipeline_root='gs://output-directory/v2-artifacts',
                  name='my-test-pipeline')
    def v2_compatible_two_step_pipeline():
      preprocess_task = preprocess_op(uri='uri-to-import', some_int=12)
      train_task = train_op(
          num_steps=preprocess_task.outputs['output_parameter_one'],
          dataset=preprocess_task.outputs['output_dataset_one'])

    self._assert_compiled_pipeline_equals_golden(
        v2_compatible_two_step_pipeline, 'v2_compatible_two_step_pipeline.yaml')


if __name__ == '__main__':
  unittest.main()