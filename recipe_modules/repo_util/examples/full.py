# Copyright 2020 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from recipe_engine.post_process import DoesNotRun, Filter, StatusFailure

DEPS = [
    'flutter/repo_util',
    'recipe_engine/context',
    'recipe_engine/file',
    'recipe_engine/path',
    'recipe_engine/properties',
    'recipe_engine/step',
]


def RunSteps(api):
  flutter_checkout_path = api.path['start_dir'].join('flutter')
  api.repo_util.checkout('flutter', flutter_checkout_path)
  api.repo_util.checkout('engine', api.path['start_dir'].join('engine'))
  api.repo_util.checkout('cocoon', api.path['start_dir'].join('cocoon'))
  api.repo_util.checkout('packages', api.path['start_dir'].join('packages'))
  env, env_paths = api.repo_util.flutter_environment(flutter_checkout_path)
  api.repo_util.engine_checkout(api.path['start_dir'].join('engine'), {}, {})
  with api.context(env=env, env_prefixes=env_paths):
    api.repo_util.sdk_checkout_path()


def GenTests(api):
  yield api.test('basic') + api.repo_util.flutter_environment_data()
  yield api.test('failed_flutter_environment')
  yield (
      api.test(
          'first_bot_update_failed',
          api.properties(
              git_url='https://github.com/flutter/engine',
              git_ref='refs/pull/1/head'
          )
      ) +
      # Next line force a fail condition for the bot update
      # first execution.
      api.step_data("Checkout source code.bot_update", retcode=1) +
      api.repo_util.flutter_environment_data()
  )
