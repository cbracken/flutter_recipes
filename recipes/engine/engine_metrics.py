# Copyright 2020 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from PB.recipes.flutter.engine import InputProperties
from PB.recipes.flutter.engine import EnvProperties

DEPS = [
    'depot_tools/bot_update',
    'depot_tools/depot_tools',
    'flutter/build_util',
    'flutter/os_utils',
    'flutter/repo_util',
    'fuchsia/goma',
    'recipe_engine/context',
    'recipe_engine/file',
    'recipe_engine/path',
    'recipe_engine/properties',
    'recipe_engine/service_account',
    'recipe_engine/step',
]
PROPERTIES = InputProperties
ENV_PROPERTIES = EnvProperties


def RunSteps(api, properties, env_properties):
  # Collect memory/cpu/process after task execution.
  api.os_utils.collect_os_info()

  checkout_path = api.path['cache'].join('builder', 'src')
  cache_root = api.path['cache'].join('builder')
  api.goma.ensure()
  dart_bin = checkout_path.join(
      'third_party', 'dart', 'tools', 'sdks', 'dart-sdk', 'bin'
  )
  android_home = checkout_path.join('third_party', 'android_tools', 'sdk')
  env = {'GOMA_DIR': api.goma.goma_dir, 'ANDROID_HOME': str(android_home)}
  env_prefixes = {'PATH': [dart_bin]}
  api.repo_util.engine_checkout(cache_root, env, env_prefixes)
  with api.depot_tools.on_path():
    api.build_util.run_gn(['--runtime-mode', 'release'], checkout_path)
    api.build_util.build('host_release', checkout_path, [])

  host_release_path = checkout_path.join('out', 'host_release')
  script_path = checkout_path.join(
      'flutter', 'testing', 'benchmark', 'generate_metrics.sh'
  )
  with api.context(env=env, env_prefixes=env_prefixes,
                   cwd=host_release_path), api.step.defer_results():
    api.step('Generate metrics', ['bash', script_path])
    # This is to clean up leaked processes.
    api.os_utils.kill_processes()
    # Collect memory/cpu/process after task execution.
    api.os_utils.collect_os_info()

  benchmark_path = checkout_path.join('flutter', 'testing', 'benchmark')
  script_path = checkout_path.join(
      'flutter', 'testing', 'benchmark', 'upload_metrics.sh'
  )

  service_account = api.service_account.default()
  access_token = service_account.get_access_token(
      scopes=[
          'https://www.googleapis.com/auth/cloud-platform',
          'https://www.googleapis.com/auth/datastore'
      ]
  )
  access_token_path = api.path.mkstemp()
  api.file.write_text(
      'write token', access_token_path, access_token, include_log=False
  )
  env['TOKEN_PATH'] = access_token_path
  env['GCP_PROJECT'] = 'flutter-cirrus'
  with api.context(env=env, env_prefixes=env_prefixes, cwd=benchmark_path):
    api.step('Upload metrics', ['bash', script_path])


def GenTests(api):
  yield api.test(
      'basic', api.properties(InputProperties(goma_jobs='200', no_lto=True))
  )
