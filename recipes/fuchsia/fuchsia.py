# Copyright 2020 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from contextlib import contextmanager
import re

DEPS = [
    'flutter/repo_util',
    'flutter/fuchsia_util',
    'recipe_engine/file',
    'recipe_engine/properties',
    'recipe_engine/path',
    'recipe_engine/context',
]


def RunSteps(api):
  checkout_path = api.path['checkout']
  api.repo_util.checkout_flutter(checkout_path, api.properties.get('git_url'),
                                 api.properties.get('git_ref'))
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
             'Read fuchsia manifest', api.file.read_json({"id": "123"})))
