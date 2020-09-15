# Copyright 2020 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from recipe_engine.recipe_api import Property

DEPS = [
    'flutter/flutter_deps',
    'flutter/repo_util',
    'flutter/os_utils',
    'recipe_engine/context',
    'recipe_engine/path',
    'recipe_engine/properties',
    'recipe_engine/raw_io',
    'recipe_engine/service_account',
    'recipe_engine/step',
]


def RunSteps(api):
  task_name = api.properties.get("task_name")
  if not task_name:
    raise ValueError('A task_name property is required')

  flutter_path = api.path['start_dir'].join('flutter')
  api.repo_util.checkout(
      'flutter',
      flutter_path,
      api.properties.get('git_url'),
      api.properties.get('git_ref'),
  )

  env, env_prefixes = api.repo_util.flutter_environment(flutter_path)
  deps = api.properties.get('dependencies', [])
  api.flutter_deps.required_deps(env, env_prefixes, deps)
  devicelab_path = flutter_path.join('dev', 'devicelab')
  with api.context(env=env, env_prefixes=env_prefixes, cwd=devicelab_path):
    api.step('flutter doctor', ['flutter', 'doctor'])
    api.step('pub get', ['pub', 'get'])
    with api.context(env=env, env_prefixes=env_prefixes):
      api.step('run %s' % task_name, ['dart', 'bin/run.dart', '-t', task_name])
  # This is a noop for non windows tasks.
  api.os_utils.kill_win_processes()


def GenTests(api):
  yield api.test(
      "no-task-name",
      api.expect_exception('ValueError'),
  )
  yield api.test(
      "basic", api.properties(task_name='abc'),
      api.repo_util.flutter_environment_data()
  )
