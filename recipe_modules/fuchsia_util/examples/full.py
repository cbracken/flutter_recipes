# Copyright 2020 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from recipe_engine.recipe_api import Property

DEPS = [
    'flutter/fuchsia_util',
    'flutter/repo_util',
    'recipe_engine/assertions',
    'recipe_engine/file',
    'recipe_engine/json',
    'recipe_engine/path',
    'recipe_engine/properties',
    'recipe_engine/swarming',
]


def RunSteps(api):
  checkout_path = api.path['checkout']
  metadata = api.fuchsia_util.run_test(checkout_path)
  api.fuchsia_util.collect_results(metadata)
  device_name = api.fuchsia_util.device_name()
  api.assertions.assertEqual(device_name, 'fuchsia-node')
  env, env_paths = api.fuchsia_util.fuchsia_environment(checkout_path)


def GenTests(api):
  # Empty calls for test functions coverage.
  api.fuchsia_util.run_test_data('name')
  api.fuchsia_util.device_name_data()
  # End of calls for test functions coverage.
  yield (api.test('basic') + api.fuchsia_util.device_name_data() +
         api.repo_util.flutter_environment_data() + api.step_data(
             'Fuchsia Tests.Create Isolate Archive.'
             'Download Fuchsia Dependencies.'
             'Read fuchsia manifest', api.file.read_json({"id": "123"})))
