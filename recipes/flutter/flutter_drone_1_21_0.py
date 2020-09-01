# Copyright 2020 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
#
# Recipe to run shard + subshard tests for the Flutter SDK repository.
# This recipe will run a single shard and will be used by flutter/flutter.py.

from contextlib import contextmanager
import re

DEPS = [
    'flutter/android_sdk',
    'flutter/json_util',
    'flutter/repo_util',
    'flutter/flutter_deps',
    'flutter/os_utils',
    'recipe_engine/context',
    'recipe_engine/isolated',
    'recipe_engine/path',
    'recipe_engine/platform',
    'recipe_engine/properties',
    'recipe_engine/step',
]


def RunShard(api, env, env_prefixes, checkout_path):
  with api.context(env=env, env_prefixes=env_prefixes, cwd=checkout_path):
    api.step(
        'run test.dart for %s shard and subshard %s' %
        (api.properties.get('shard'), api.properties.get('subshard')),
        ['dart', checkout_path.join('dev', 'bots', 'test.dart')]
    )


def RunWithAndroid(api, env, env_prefixes, checkout_path):
  api.android_sdk.install()
  with api.android_sdk.context():
    RunShard(api, env, env_prefixes, checkout_path)


def RunSteps(api):
  checkout_path = api.path['start_dir'].join('flutter')
  api.repo_util.checkout(
      'flutter',
      checkout_path=checkout_path,
      url=api.properties.get('git_url'),
      ref=api.properties.get('git_ref')
  )

  if api.platform.is_linux:
    # Validates flutter builders json format.
    api.json_util.validate_json(checkout_path)

  env, env_prefixes = api.repo_util.flutter_environment(checkout_path)
  api.flutter_deps.chrome_and_driver(env, env_prefixes)
  api.flutter_deps.open_jdk(env, env_prefixes)
  api.flutter_deps.goldctl(env, env_prefixes)
  # Add shard and subshard.
  env['SHARD'] = api.properties.get('shard')
  env['SUBSHARD'] = api.properties.get('subshard')
  with api.context(env=env, env_prefixes=env_prefixes, cwd=checkout_path):
    api.step('flutter doctor', ['flutter', 'doctor'])
    api.step('download dependencies', ['flutter', 'update-packages'])
    if 'android_sdk' in api.properties.get('dependencies', []):
      RunWithAndroid(api, env, env_prefixes, checkout_path)
    else:
      RunShard(api, env, env_prefixes, checkout_path)

  # This is a noop for non windows tasks.
  api.os_utils.kill_win_processes()


def GenTests(api):
  yield api.test('no_requirements', api.repo_util.flutter_environment_data())
  yield api.test(
      'android_sdk', api.repo_util.flutter_environment_data(),
      api.properties(
          dependencies=['android_sdk'],
          android_sdk=True,
          android_sdk_preview_license='abc',
          android_sdk_license='cde'
      )
  )
