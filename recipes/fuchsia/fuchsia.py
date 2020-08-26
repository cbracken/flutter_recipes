# Copyright 2020 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from contextlib import contextmanager
import re

DEPS = [
    'flutter/repo_util',
    'flutter/fuchsia_util',
    'recipe_engine/cipd',
    'recipe_engine/file',
    'recipe_engine/properties',
    'recipe_engine/path',
    'recipe_engine/context',
]


def RunSteps(api):
  checkout_path = api.path['start_dir'].join('flutter')
  api.repo_util.checkout(
      'flutter',
      checkout_path,
      api.properties.get('git_url'),
      api.properties.get('git_ref'),
  )
  env, env_prefixes = api.repo_util.flutter_environment(checkout_path)
  with api.context(env=env, env_prefixes=env_prefixes, cwd=checkout_path):
    metadata = api.fuchsia_util.run_test(checkout_path)
    api.fuchsia_util.collect_results(metadata)


def GenTests(api):
  yield (api.test('basic') + api.properties(
      git_url='https://github.com/flutter/flutter',
      git_ref='refs/pull/1/head',
      shard='tests',
      os='linux',
      fuchsia_ctl_version='version:0.0.2',
      should_upload=False) + api.fuchsia_util.run_test_data(
          'Fuchsia Tests.Trigger Fuchsia Driver Tests') +
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
