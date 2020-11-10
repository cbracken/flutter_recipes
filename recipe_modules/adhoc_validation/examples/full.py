# Copyright 2020 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from recipe_engine.post_process import DoesNotRun, Filter, StatusFailure

DEPS = [
    'flutter/adhoc_validation', 'flutter/repo_util', 'recipe_engine/context',
    'recipe_engine/path', 'recipe_engine/platform', 'recipe_engine/properties'
]


def RunSteps(api):
  validation = api.properties.get('validation', 'docs')
  env, env_prefixes = api.repo_util.flutter_environment(
      api.path['start_dir'].join('flutter sdk')
  )
  with api.context(env=env, env_prefixes=env_prefixes):
    api.adhoc_validation.run('Docs', validation, {}, {})


def GenTests(api):
  checkout_path = api.path['start_dir'].join('flutter sdk')
  yield api.test(
      'win', api.platform.name('win'),
      api.repo_util.flutter_environment_data(checkout_path)
  )
  yield api.test(
      'linux', api.platform.name('linux'),
      api.properties(firebase_project='myproject'),
      api.repo_util.flutter_environment_data(checkout_path)
  )
  yield api.test(
      'mac', api.platform.name('mac'),
      api.properties(dependencies=[{"dependency": "xcode"}]),
      api.repo_util.flutter_environment_data(checkout_path)
  )
  yield api.test(
      'mac_nodeps', api.platform.name('mac'),
      api.repo_util.flutter_environment_data(checkout_path)
  )
  yield api.test(
      'invalid_validation', api.properties(validation='invalid'),
      api.expect_exception('AssertionError'),
      api.repo_util.flutter_environment_data(checkout_path)
  )
