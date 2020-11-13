# Copyright 2020 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
#
# Recipe to run shard + subshard tests for the Flutter SDK repository.
# This recipe will run a single shard and will be used by flutter/flutter.py.

from contextlib import contextmanager
import re

DEPS = [
    'depot_tools/osx_sdk',
    'flutter/android_sdk',
    'flutter/repo_util',
    'flutter/flutter_deps',
    'flutter/os_utils',
    'recipe_engine/context',
    'recipe_engine/path',
    'recipe_engine/properties',
    'recipe_engine/step',
]


def RunShard(api, env, env_prefixes, checkout_path):
  with api.context(env=env, env_prefixes=env_prefixes, cwd=checkout_path):
    cmd_list = [
        'dart', '--enable-asserts',
        checkout_path.join('dev', 'bots', 'test.dart')
    ]
    if env.get('LOCAL_ENGINE'):
      cmd_list.extend(['--local-engine', env.get('LOCAL_ENGINE')])

    api.step(
        'run test.dart for %s shard and subshard %s' %
        (api.properties.get('shard'), api.properties.get('subshard')), cmd_list
    )


def RunSteps(api):
  # Collect memory/cpu/process before task execution.
  api.os_utils.collect_os_info()

  checkout_path = api.path['start_dir'].join('flutter')
  api.repo_util.checkout(
      'flutter',
      checkout_path=checkout_path,
      url=api.properties.get('git_url'),
      ref=api.properties.get('git_ref')
  )

  env, env_prefixes = api.repo_util.flutter_environment(checkout_path)
  deps = api.properties.get('dependencies', [])
  api.flutter_deps.required_deps(env, env_prefixes, deps)
  # Add shard and subshard.
  env['SHARD'] = api.properties.get('shard')
  env['SUBSHARD'] = api.properties.get('subshard')
  # Load local engine information if available.
  api.flutter_deps.flutter_engine(env, env_prefixes)

  with api.context(env=env, env_prefixes=env_prefixes, cwd=checkout_path):
    api.step('flutter doctor', ['flutter', 'doctor', '-v'])
    api.step('download dependencies', ['flutter', 'update-packages'])
    dep_list = [d['dependency'] for d in deps]
    if 'xcode' in dep_list:
      with api.osx_sdk('ios'), api.step.defer_results():
        api.flutter_deps.swift()
        api.flutter_deps.gems(
            env, env_prefixes, checkout_path.join('dev', 'ci', 'mac')
        )
        RunShard(api, env, env_prefixes, checkout_path)
        # This is to clean up leaked processes.
        api.os_utils.kill_processes()
        # Collect memory/cpu/process after task execution.
        api.os_utils.collect_os_info()
    else:
      with api.step.defer_results():
        RunShard(api, env, env_prefixes, checkout_path)
        # This is to clean up leaked processes.
        api.os_utils.kill_processes()
        # Collect memory/cpu/process after task execution.
        api.os_utils.collect_os_info()


def GenTests(api):
  yield api.test('no_requirements', api.repo_util.flutter_environment_data())
  yield api.test(
      'android_sdk', api.repo_util.flutter_environment_data(),
      api.properties(
          dependencies=[{'dependency': 'android_sdk'}],
          android_sdk=True,
          android_sdk_preview_license='abc',
          android_sdk_license='cde'
      )
  )
  yield api.test(
      'web_engine', api.repo_util.flutter_environment_data(),
      api.properties(isolated_hash='abceqwe',)
  )
  yield api.test(
      'xcode', api.repo_util.flutter_environment_data(),
      api.properties(dependencies=[{'dependency': 'xcode'}],)
  )
