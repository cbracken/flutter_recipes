# Copyright 2020 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Recipe for engine shards.

   web_engine.py will call these shards. It will build the Flutter Web Engine,
   and will archive it to the isolate server.

   These shards will be called with required dependencies, felt commands, and
   with an isolate hash of the Flutter Web Engine.
"""

import contextlib
import copy

from recipe_engine import recipe_api

from PB.recipes.flutter.engine import InputProperties
from PB.recipes.flutter.engine import EnvProperties

DEPS = [
    'depot_tools/bot_update',
    'depot_tools/depot_tools',
    'depot_tools/osx_sdk',
    'flutter/flutter_deps',
    'flutter/os_utils',
    'flutter/json_util',
    'flutter/repo_util',
    'flutter/web_util',
    'fuchsia/goma',
    'recipe_engine/context',
    'recipe_engine/file',
    'recipe_engine/json',
    'recipe_engine/path',
    'recipe_engine/platform',
    'recipe_engine/properties',
    'recipe_engine/runtime',
    'recipe_engine/step',
]

GIT_REPO = (
    'https://chromium.googlesource.com/external/github.com/flutter/engine'
)

PROPERTIES = InputProperties
ENV_PROPERTIES = EnvProperties


def GetCheckoutPath(api):
  """Path to checkout the flutter/engine repo."""
  return api.path['cleanup'].join('builder', 'src')


def RunSteps(api, properties, env_properties):
  """Steps to checkout flutter engine and execute web test shard.

  The test shard to run will be determined by `command_args` send as part of
  properties.
  """
  cache_root = api.path['cleanup'].join('builder')
  checkout = GetCheckoutPath(api)
  platform = api.platform.name.capitalize()
  if properties.clobber:
    api.file.rmtree('Clobber cache', cache_root)
  api.file.rmtree('Clobber build output: %s' % platform, checkout.join('out'))

  api.file.ensure_directory('Ensure checkout cache', cache_root)
  api.goma.ensure()
  env = {}
  env_prefixes = {}

  # Checkout source code and build
  api.repo_util.engine_checkout(cache_root, env, env_prefixes)

  # Prepare the dependencies that web tests need.
  # These can be browsers, web drivers or other repositories.
  api.web_util.prepare_dependencies(checkout)

  with api.context(cwd=cache_root, env=env,
                   env_prefixes=env_prefixes), api.depot_tools.on_path():

    target_name = 'host_debug_unopt'

    # Load local engine information if available.
    api.flutter_deps.flutter_engine(env, env_prefixes)

    android_home = checkout.join('third_party', 'android_tools', 'sdk')
    env['GOMA_DIR'] = api.goma.goma_dir
    env['ANDROID_HOME'] = str(android_home)
    env['CHROME_NO_SANDBOX'] = 'true'
    env['ENGINE_PATH'] = cache_root
    # flutter_engine deps adds dart dependency as out/host_debug_unopt/dart-sdk
    # We are changing it with src/third_party/dart/tools/sdks/dart-sdk
    dart_bin = checkout.join(
        'third_party', 'dart', 'tools', 'sdks', 'dart-sdk', 'bin'
    )
    paths = env_prefixes.get('PATH', [])
    paths.insert(0, dart_bin)
    env_prefixes['PATH'] = paths

    command_args = api.properties.get('command_args', ['test'])
    command_name = api.properties.get('command_name', 'test')
    felt_cmd = [
        checkout.join('out', target_name, 'dart-sdk', 'bin', 'dart'),
        'dev/felt.dart'
    ]
    felt_cmd.extend(command_args)

    with api.context(cwd=cache_root, env=env,
                     env_prefixes=env_prefixes), api.depot_tools.on_path():
      # Update dart packages and run tests.
      local_engine_path = env.get('LOCAL_ENGINE')
      local_pub = local_engine_path.join('dart-sdk', 'bin', 'pub')
      with api.context(
          cwd=checkout.join('flutter', 'web_sdk', 'web_engine_tester')):
        api.step('pub get in web_engine_tester', [local_pub, 'get'])
      with api.context(cwd=checkout.join('flutter', 'lib', 'web_ui')):
        api.step('pub get in web_ui', [local_pub, 'get'])
        if api.platform.is_mac:
          with api.osx_sdk('ios'):
            with recipe_api.defer_results():
              api.step('felt test: %s' % command_name, felt_cmd)
              if api.properties.get('dependencies'
                                   ) and 'goldens_repo' in api.properties.get(
                                       'dependencies'):
                api.web_util.upload_failing_goldens(checkout, 'ios-safari')
              # This is to clean up leaked processes.
              api.os_utils.kill_processes()
              # Collect memory/cpu/process after task execution.
              api.os_utils.collect_os_info()
        else:
          with recipe_api.defer_results():
            api.step('felt test: %s' % command_name, felt_cmd)
            if api.properties.get('dependencies'
                                 ) and 'goldens_repo' in api.properties.get(
                                     'dependencies'):
              api.web_util.upload_failing_goldens(checkout, 'chrome')
            # This is to clean up leaked processes.
            api.os_utils.kill_processes()
            # Collect memory/cpu/process after task execution.
            api.os_utils.collect_os_info()


def GenTests(api):
  golden_yaml_file = {'repository': 'repo', 'revision': 'b6efc758'}
  browser_yaml_file = {
      'required_driver_version': {'chrome': 84},
      'chrome': {'Linux': '768968', 'Mac': '768985', 'Win': '768975'}
  }
  yield api.test(
      'linux-post-submit',
      api.step_data(
          'read browser lock yaml.parse', api.json.output(browser_yaml_file)
      ),
      api.step_data(
          'read browser lock yaml (2).parse',
          api.json.output(browser_yaml_file)
      ), api.step_data('read yaml.parse', api.json.output(golden_yaml_file)),
      api.properties(
          goma_jobs='200',
          gcs_goldens_bucket='mybucket',
          dependencies=['chrome_driver', 'chrome', 'goldens_repo'],
          command_args=['test', '--browser=chrome', '--integration-tests-only'],
          command_name='chrome-integration-tests',
          isolated_hash='abceqwe'
      ), api.platform('linux', 64)
  ) + api.runtime(is_experimental=False) + api.platform.name('linux')
  yield api.test(
      'linux-firefox-integration',
      api.step_data('read yaml.parse', api.json.output(golden_yaml_file)),
      api.properties(
          goma_jobs='200',
          gcs_goldens_bucket='mybucket',
          dependencies=['firefox_driver', 'goldens_repo'],
          command_args=[
              'test', '--browser=firefox', '--integration-tests-only'
          ],
          command_name='firefox-integration-tests',
          isolated_hash='abceqwe'
      ), api.platform.name('linux'), api.platform('linux', 64)
  ) + api.runtime(is_experimental=False)
  yield api.test('windows-post-submit') + api.properties(
      goma_jobs='200', isolated_hash='abceqwe'
  ) + api.platform('win', 32) + api.runtime(is_experimental=False)
  yield api.test(
      'mac-post-submit',
      api.step_data('read yaml.parse', api.json.output(golden_yaml_file)),
      api.properties(
          goma_jobs='200',
          gcs_goldens_bucket='mybucket',
          dependencies=['goldens_repo'],
          command_args=['test', '--browser=ios-safari', '--unit-tests-only'],
          command_name='ios-safari-unit-tests',
          isolated_hash='abceqwe'
      ), api.platform('mac', 64)
  ) + api.runtime(is_experimental=False)
  yield api.test(
      'linux-experimental',
      api.step_data('read yaml.parse', api.json.output(golden_yaml_file)),
      api.repo_util.flutter_environment_data(),
      api.properties(
          goma_jobs='200',
          git_url='https://mygitrepo',
          git_ref='refs/pull/1/head',
          dependencies=['goldens_repo'],
          clobber=True,
          isolated_hash='abceqwe'
      ), api.platform('linux', 64)
  ) + api.runtime(is_experimental=True)
  yield api.test(
      'linux-error',
      api.properties(
          goma_jobs='200',
          git_url='https://mygitrepo',
          git_ref='refs/pull/1/head',
          dependencies=['invalid_dependency'],
          clobber=True,
          isolated_hash='abceqwe'
      ), api.platform('linux', 64), api.expect_exception('ValueError')
  ) + api.runtime(is_experimental=True)
