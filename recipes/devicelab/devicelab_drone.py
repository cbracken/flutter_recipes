# Copyright 2020 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from recipe_engine.recipe_api import Property

DEPS = [
    'depot_tools/osx_sdk',
    'flutter/flutter_deps',
    'flutter/repo_util',
    'flutter/os_utils',
    'recipe_engine/buildbucket',
    'recipe_engine/context',
    'recipe_engine/file',
    'recipe_engine/path',
    'recipe_engine/properties',
    'recipe_engine/raw_io',
    'recipe_engine/service_account',
    'recipe_engine/step',
    'recipe_engine/swarming',
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
  # Run test
  test_runner_command = ['dart', 'bin/run.dart', '-t', task_name]
  # Create service account for post submit tests.
  if api.properties.get('upload_metrics'):
    service_account = api.service_account.default()
    access_token = service_account.get_access_token()
    access_token_path = api.path.mkstemp()
    git_branch = api.buildbucket.gitiles_commit.ref.replace(
        'refs/heads/', ''
    )
    api.file.write_text(
        "write token", access_token_path, access_token, include_log=False
    )
    test_runner_command.extend([
        '--service-account-token-file', access_token_path,
        '--luci-builder', api.properties.get('buildername'),
        # LUCI git checkouts end up in a detached HEAD state, so branch must
        # be passed from gitiles -> test runner -> Cocoon.
        '--git-branch', git_branch
    ])
  # Gems are installed differently new and old versions of xcode. Pre xcode 12
  # the ruby sdk included in xcode was able to compile the gems correctly but
  # with xcode 12 gems building from inside a xcode context fails. We use the
  # bot name to identify if the builder is running on a devicelab bot which will
  # be running xcode 12.
  bot_id = api.swarming.bot_id
  is_devicelab_bot = bot_id.startswith('flutter-devicelab')
  with api.context(env=env, env_prefixes=env_prefixes, cwd=devicelab_path):
    api.step('flutter doctor', ['flutter', 'doctor', '--verbose'])
    api.step('flutter update-packages', ['flutter', 'update-packages'])
    api.step('pub get', ['pub', 'get'])
    dep_list = {d['dependency']: d.get('version') for d in deps}
    if dep_list.has_key('xcode'):
      api.os_utils.clean_derived_data()
      # Build gems here for xcode 12 or newer.
      if is_devicelab_bot:
        api.flutter_deps.gems(
            env, env_prefixes, flutter_path.join('dev', 'ci', 'mac')
        )
      with api.osx_sdk('ios'):
        api.flutter_deps.swift(dep_list.get('swift', 'latest'))
        # Build gems here for xcode older than 12 we'll need to delete
        # this path after migrating sdk and devicelab to xcode 12.
        if not is_devicelab_bot:
          api.flutter_deps.gems(
              env, env_prefixes, flutter_path.join('dev', 'ci', 'mac')
          )
        api.os_utils.shutdown_simulators()
        with api.context(env=env,
                         env_prefixes=env_prefixes), api.step.defer_results():
          api.step('run %s' % task_name, test_runner_command)
          # This is to clean up leaked processes.
          api.os_utils.kill_processes()
          # Collect memory/cpu/process after task execution.
          api.os_utils.collect_os_info()
    else:
      with api.context(env=env,
                       env_prefixes=env_prefixes), api.step.defer_results():
        api.step('run %s' % task_name, test_runner_command)
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
      "basic",
      api.properties(task_name='abc'),
      api.repo_util.flutter_environment_data(),
  )
  yield api.test(
      "xcode-devicelab",
      api.properties(
          task_name='abc',
          dependencies=[{'dependency': 'xcode'},
                        {'dependency': 'swift', 'version': 'abc'}]
      ), api.repo_util.flutter_environment_data(),
      api.swarming.properties(bot_id='flutter-devicelab-mac-1')
  )
  yield api.test(
      "xcode-chromium-mac",
      api.properties(
          task_name='abc',
          dependencies=[{'dependency': 'xcode'},
                        {'dependency': 'swift', 'version': 'abc'}]
      ),
      api.repo_util.flutter_environment_data(),
  )
  yield api.test(
      "post-submit",
      api.properties(
          buildername='Linux abc',
          pool='flutter.luci.prod',
          task_name='abc',
          upload_metrics=True
      ), api.repo_util.flutter_environment_data()
  )
