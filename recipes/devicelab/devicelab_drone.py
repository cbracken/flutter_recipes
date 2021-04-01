# Copyright 2020 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from recipe_engine.recipe_api import Property

DEPS = [
    'flutter/bucket_util',
    'flutter/devicelab_osx_sdk',
    'flutter/flutter_deps',
    'flutter/logs_util',
    'flutter/repo_util',
    'flutter/os_utils',
    'flutter/osx_sdk',
    'recipe_engine/buildbucket',
    'recipe_engine/context',
    'recipe_engine/file',
    'recipe_engine/path',
    'recipe_engine/properties',
    'recipe_engine/raw_io',
    'recipe_engine/runtime',
    'recipe_engine/service_account',
    'recipe_engine/step',
    'recipe_engine/swarming',
]


def RunSteps(api):
  task_name = api.properties.get("task_name")
  if not task_name:
    raise ValueError('A task_name property is required')

  flutter_path = api.path.mkdtemp().join('flutter sdk')
  api.repo_util.checkout(
      'flutter',
      flutter_path,
      api.properties.get('git_url'),
      api.properties.get('git_ref'),
  )
  env, env_prefixes = api.repo_util.flutter_environment(flutter_path)
  api.logs_util.initialize_logs_collection(env)
  with api.step.nest('Dependencies'):
    deps = api.properties.get('dependencies', [])
    api.flutter_deps.required_deps(env, env_prefixes, deps)
    api.flutter_deps.vpython(env, env_prefixes, 'latest')
  devicelab_path = flutter_path.join('dev', 'devicelab')
  git_branch = api.buildbucket.gitiles_commit.ref.replace('refs/heads/', '')
  # Create tmp file to store results in
  results_path = api.path.mkstemp()
  # Run test
  runner_params = [
      '-t', task_name, '--results-file', results_path, '--luci-builder',
      api.properties.get('buildername')
  ]
  # LUCI git checkouts end up in a detached HEAD state, so branch must
  # be passed from gitiles -> test runner -> Cocoon.
  if git_branch:
    # git_branch is set only when the build was triggered by buildbucket.
    runner_params.extend(['--git-branch', git_branch])
  with api.context(env=env, env_prefixes=env_prefixes, cwd=devicelab_path):
    api.step(
        'flutter doctor',
        ['flutter', 'doctor'],
    )
    api.step('pub get', ['pub', 'get'], infra_step=True)
    dep_list = {d['dependency']: d.get('version') for d in deps}
    if dep_list.has_key('xcode'):
      api.os_utils.clean_derived_data()
      if str(api.swarming.bot_id).startswith('flutter-devicelab'):
        with api.devicelab_osx_sdk('ios'):
          mac_test(
              api, env, env_prefixes, flutter_path, task_name, runner_params
          )
      else:
        with api.osx_sdk('ios'):
          mac_test(
              api, env, env_prefixes, flutter_path, task_name, runner_params
          )
    else:
      with api.context(env=env,
                       env_prefixes=env_prefixes), api.step.defer_results():
        api.step('flutter doctor', ['flutter', 'doctor', '--verbose'])
        test_runner_command = ['dart', 'bin/run.dart']
        test_runner_command.extend(runner_params)
        api.step('run %s' % task_name, test_runner_command)
        api.logs_util.upload_logs(task_name)
        # This is to clean up leaked processes.
        api.os_utils.kill_processes()

  with api.context(env=env, env_prefixes=env_prefixes, cwd=devicelab_path):
    uploadMetrics(api, results_path)


def mac_test(api, env, env_prefixes, flutter_path, task_name, runner_params):
  """Runs a devicelab mac test."""
  api.flutter_deps.gems(
      env, env_prefixes, flutter_path.join('dev', 'ci', 'mac')
  )
  api.step('flutter doctor', ['flutter', 'doctor', '--verbose'])
  api.os_utils.dismiss_dialogs()
  api.os_utils.shutdown_simulators()
  with api.context(env=env,
                   env_prefixes=env_prefixes), api.step.defer_results():
    resource_name = api.resource('runner.sh')
    api.step('Set execute permission', ['chmod', '755', resource_name])
    test_runner_command = [resource_name]
    test_runner_command.extend(runner_params)
    api.step('run %s' % task_name, test_runner_command)
    api.logs_util.upload_logs(task_name)
    # This is to clean up leaked processes.
    api.os_utils.kill_processes()


def uploadMetrics(api, results_path):
  """Upload DeviceLab test performance metrics to Cocoon.

  luci-auth only gurantees a service account token life of 3 minutes. To work
  around this limitation, results uploading is separate from the the test run.
  """
  if not api.properties.get('upload_metrics') or api.runtime.is_experimental:
    return
  with api.step.nest('Upload metrics'):
    service_account = api.service_account.default()
    access_token = service_account.get_access_token()
    access_token_path = api.path.mkstemp()
    api.file.write_text(
        "write token", access_token_path, access_token, include_log=False
    )
    upload_command = [
        'dart', 'bin/test_runner.dart', 'upload-metrics', '--results-file',
        results_path, '--service-account-token-file', access_token_path
    ]
    api.step('upload metrics', upload_command, infra_step=True)


def GenTests(api):
  checkout_path = api.path['cleanup'].join('tmp_tmp_1', 'flutter sdk')
  yield api.test(
      "no-task-name",
      api.expect_exception('ValueError'),
  )
  yield api.test(
      "basic", api.properties(buildername='Linux abc', task_name='abc'),
      api.repo_util.flutter_environment_data(checkout_dir=checkout_path),
      api.buildbucket.ci_build(
          project='test',
          git_repo='git.example.com/test/repo',
      )
  )
  yield api.test(
      "xcode-devicelab",
      api.properties(
          buildername='Mac abc',
          task_name='abc',
          dependencies=[{'dependency': 'xcode'}]
      ), api.repo_util.flutter_environment_data(checkout_dir=checkout_path),
      api.swarming.properties(bot_id='flutter-devicelab-mac-1')
  )
  yield api.test(
      "xcode-chromium-mac",
      api.properties(
          buildername='Mac abc',
          task_name='abc',
          dependencies=[{'dependency': 'xcode'}]
      ),
      api.repo_util.flutter_environment_data(checkout_dir=checkout_path),
  )
  yield api.test(
      "post-submit",
      api.properties(
          buildername='Linux abc', task_name='abc', upload_metrics=True
      ), api.repo_util.flutter_environment_data(checkout_dir=checkout_path)
  )
  yield api.test(
      "upload-metrics-mac",
      api.properties(
          buildername='Mac abc',
          dependencies=[{'dependency': 'xcode'}],
          task_name='abc',
          upload_metrics=True
      ), api.repo_util.flutter_environment_data(checkout_dir=checkout_path)
  )
