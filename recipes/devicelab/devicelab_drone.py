# Copyright 2020 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from recipe_engine.recipe_api import Property

DEPS = [
    'depot_tools/osx_sdk',
    'flutter/flutter_deps',
    'flutter/repo_util',
    'flutter/os_utils',
    'recipe_engine/context',
    'recipe_engine/path',
    'recipe_engine/properties',
    'recipe_engine/raw_io',
    'recipe_engine/service_account',
    'recipe_engine/swarming',
    'recipe_engine/step',
]


def RunSteps(api):
  # Collect memory/cpu/process before task execution.
  api.os_utils.collect_os_info()

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
    api.step('flutter doctor', ['flutter', 'doctor', '--verbose'])
    api.step('pub get', ['pub', 'get'])
    dep_list = {d['dependency']: d.get('version') for d in deps}
    if dep_list.has_key('xcode'):
      api.os_utils.clean_derived_data()
      with api.osx_sdk('ios'):
        api.flutter_deps.swift(dep_list.get('swift', 'latest'))
        api.flutter_deps.gems(
            env, env_prefixes, flutter_path.join('dev', 'ci', 'mac')
        )
        api.os_utils.shutdown_simulators()
        with api.context(env=env,
                         env_prefixes=env_prefixes), api.step.defer_results():
          api.step(
              'run %s' % task_name, ['dart', 'bin/run.dart', '-t', task_name]
          )
          # This is to clean up leaked processes.
          api.os_utils.kill_processes()
          # Collect memory/cpu/process after task execution.
          api.os_utils.collect_os_info()
    else:
      with api.context(env=env,
                       env_prefixes=env_prefixes), api.step.defer_results():
        api.step(
            'run %s' % task_name, ['dart', 'bin/run.dart', '-t', task_name]
        )
        # This is to clean up leaked processes.
        api.os_utils.kill_processes()
        # Collect memory/cpu/process after task execution.
        api.os_utils.collect_os_info()


def GenTests(api):
  yield api.test(
      "no-task-name",
      api.expect_exception('ValueError'),
  )
  yield api.test(
      "basic", api.properties(task_name='abc'),
      api.repo_util.flutter_environment_data()
  )
  yield api.test(
      "xcode",
      api.properties(
          task_name='abc',
          dependencies=[{'dependency': 'xcode'},
                        {'dependency': 'swift', 'version': 'abc'}]
      ),
      api.repo_util.flutter_environment_data(),
  )
