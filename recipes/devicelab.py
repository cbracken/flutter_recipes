# Copyright 2020 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from recipe_engine.recipe_api import Property

DEPS = [
    'depot_tools/git',
    'depot_tools/osx_sdk',
    'flutter/android_sdk',
    'flutter/repo_util',
    'flutter/yaml',
    'recipe_engine/cipd',
    'recipe_engine/context',
    'recipe_engine/file',
    'recipe_engine/json',
    'recipe_engine/path',
    'recipe_engine/platform',
    'recipe_engine/properties',
    'recipe_engine/raw_io',
    'recipe_engine/step',
]

PROPERTIES = {
    'task_name': Property(kind=str, help='Name of the devicelab task to run'),
}


def RunSteps(api, task_name):
  flutter_path = api.path['start_dir'].join('flutter')
  with api.step.nest('checkout flutter/flutter'):
    api.repo_util.checkout(
        'flutter',
        flutter_path,
        api.properties.get('git_url'),
        api.properties.get('git_ref'),
    )
  env, env_prefixes = api.repo_util.flutter_environment(flutter_path)
  devicelab_path = flutter_path.join('dev', 'devicelab')
  with api.context(env=env, env_prefixes=env_prefixes, cwd=devicelab_path):
    api.step('flutter doctor', ['flutter', 'doctor'])

    # Reads the manifest.
    result = api.yaml.read('read manifest',
                           devicelab_path.join('manifest.yaml'),
                           api.json.output())
    manifest = result.json.output

    # Verifies that the manifest contains the task to run.
    task = manifest['tasks'].get(task_name)
    if not task:
      raise ValueError('Unknown task: %s' % task_name)

    # Example first capability values: linux/android, mac/ios.
    first_capability = task['required_agent_capabilities'][0]
    sdk = first_capability.split('/')[1]

    # Runs a task.
    api.step('pub get', ['pub', 'get'])
    if sdk == 'android':
      run_android_task(api, task_name)
    elif sdk == 'ios':
      run_ios_task(api, task_name)


def run_android_task(api, task_name):
  api.android_sdk.install()
  with api.android_sdk.context():
    api.step('run %s' % task_name, ['dart', 'bin/run.dart', '-t', task_name])


def run_ios_task(api, task_name):
  api.step('unlock login keychain', ['unlock_login_keychain.sh'])
  # See go/googler-flutter-signing about how to renew the Apple development
  # certificate and provisioning profile.
  code_signing_env = {
      'FLUTTER_XCODE_CODE_SIGN_STYLE': 'Manual',
      'FLUTTER_XCODE_DEVELOPMENT_TEAM': 'S8QB4VV633',
      'FLUTTER_XCODE_PROVISIONING_PROFILE_SPECIFIER': 'match Development *',
  }
  with api.context(env=code_signing_env):
    api.step('run %s' % task_name, ['dart', 'bin/run.dart', '-t', task_name])


def GenTests(api):
  yield api.test(
      'missing_task_name',
      api.expect_exception('ValueError'),
  )

  sample_manifest = {
      "tasks": {
          "android_defines_test": {
              "description": "Builds an APK with a --dart-define ...",
              "stage": "devicelab",
              "required_agent_capabilities": ["linux/android"],
          },
          "flavors_test": {
              "description": "Checks that flavored builds work on Android.",
              "stage": "devicelab",
              "required_agent_capabilities": ["mac/android"],
          },
          "flutter_gallery_ios__compile": {
              "description": "Collects various performance metrics of ...",
              "stage": "devicelab_ios",
              "required_agent_capabilities": ["mac/ios"],
          },
      },
  }

  yield api.test(
      'unknown_task',
      api.properties(task_name='unknown_task'),
      api.repo_util.flutter_environment_data(),
      api.step_data('read manifest.parse', api.json.output(sample_manifest)),
      api.expect_exception('ValueError'),
  )

  for task_name in [
      'android_defines_test', 'flavors_test', 'flutter_gallery_ios__compile'
  ]:
    yield api.test(
        task_name,
        api.properties(
            git_ref='refs/pull/123/head', git_url='https://abc.com/repo'),
        api.properties(
            task_name=task_name,
            android_sdk_license='android_sdk_hash',
            android_sdk_preview_license='android_sdk_preview_hash',
        ),
        api.repo_util.flutter_environment_data(),
        api.step_data('read manifest.parse', api.json.output(sample_manifest)),
    )
