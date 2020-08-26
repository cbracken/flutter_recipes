# Copyright 2020 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from recipe_engine.recipe_api import Property

DEPS = [
    'flutter/fuchsia_util',
    'flutter/repo_util',
    'recipe_engine/assertions',
    'recipe_engine/cipd',
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
             'Read fuchsia cipd version',
             api.file.read_text('FuchsiaSdkCipdVersion')) + api.step_data(
                 'Fuchsia Tests.Create Isolate Archive.'
                 'Download Fuchsia Dependencies.'
                 'cipd describe fuchsia/sdk/core/linux-amd64',
                 api.cipd.example_describe(
                     package_name="fuchsia/sdk/core/linux-amd64",
                     version="FuchsiaSdkCipdVersion",
                     test_data_tags=[
                         "git_revision:GIT_REVISION", "jiri:JIRI_VERSION",
                         "version:FUCHSIA_VERSION"
                     ])))
  yield api.test('fuchsia_sdk_version_error') + api.step_data(
      'Fuchsia Tests.Create Isolate Archive.'
      'Download Fuchsia Dependencies.'
      'Read fuchsia cipd version',
      api.file.read_text('FuchsiaSdkCipdVersion')) + api.step_data(
          'Fuchsia Tests.Create Isolate Archive.'
          'Download Fuchsia Dependencies.'
          'cipd describe fuchsia/sdk/core/linux-amd64',
          api.cipd.example_describe(
              package_name="fuchsia/sdk/core/linux-amd64",
              version="FuchsiaSdkCipdVersion",
              test_data_tags=[]))
