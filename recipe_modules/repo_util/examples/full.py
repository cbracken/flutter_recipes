# Copyright 2020 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from recipe_engine.post_process import DoesNotRun, Filter, StatusFailure

DEPS = [
    'flutter/repo_util',
    'recipe_engine/path',
]


def RunSteps(api):
  checkout_path = api.path['checkout']
  api.repo_util.checkout_flutter(checkout_path)
  api.repo_util.checkout_engine(checkout_path)
  api.repo_util.checkout_cocoon(checkout_path)
  env, env_paths = api.repo_util.flutter_environment(checkout_path)


def GenTests(api):
  yield api.test('basic') + api.repo_util.flutter_environment_data()
  yield api.test('failed_flutter_environment')
