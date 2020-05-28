# Copyright 2020 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from recipe_engine.recipe_api import Property

DEPS = [
    'depot_tools/git',
    'recipe_engine/cipd',
    'recipe_engine/context',
    'recipe_engine/file',
    'recipe_engine/json',
    'recipe_engine/path',
    'recipe_engine/platform',
    'recipe_engine/properties',
    'recipe_engine/step',
    'android_sdk',
    'repo_util',
    'yaml',
]

PROPERTIES = {
    'task_name': Property(kind=str, help='Name of the devicelab task to run'),
}


def RunSteps(api, task_name):
  flutter_path = api.path['start_dir'].join('flutter')
  api.repo_util.checkout(
      'flutter',
      flutter_path,
      api.properties.get('git_url'),
      api.properties.get('git_ref'),
  )
  api.step(
      'flutter doctor', cmd=[flutter_path.join('bin', 'flutter'), 'doctor'])

  # Reads the manifest.
  devicelab_path = flutter_path.join('dev', 'devicelab')
  manifest_yaml_path = devicelab_path.join('manifest.yaml')
  result = api.yaml.read('read manifest', manifest_yaml_path, api.json.output())
  manifest = result.json.output

  # Verifies the manifest containing the task to run.
  if task_name not in manifest['tasks']:
    raise ValueError('Unknown task: %s' % task_name)

  env, env_prefixes = api.repo_util.flutter_environment(flutter_path)
  with api.context(env=env, env_prefixes=env_prefixes, cwd=devicelab_path):
    api.step('pub get', cmd=['pub', 'get'])
    api.android_sdk.install()
    with api.android_sdk.context():
      api.step(
          'run %s' % task_name, cmd=['dart', 'bin/run.dart', '-t', task_name])


def GenTests(api):
  yield api.test(
      'missing_task_name',
      api.expect_exception('ValueError'),
  )
  example_manifest = {"tasks": {"task1": {}, "task2": {}}}
  yield api.test(
      'unknown_task',
      api.properties(task_name='unknown_task'),
      api.step_data('read manifest.parse', api.json.output(example_manifest)),
      api.expect_exception('ValueError'),
  )
  yield api.test(
      'example_task',
      api.properties(
          git_ref='refs/pull/123/head', git_url='https://abc.com/repo'),
      api.properties(
          task_name='task1',
          android_sdk_license='android_sdk_hash',
          android_sdk_preview_license='android_sdk_preview_hash',
      ),
      api.repo_util.flutter_environment_data(),
      api.step_data('read manifest.parse', api.json.output(example_manifest)),
      api.post_check(lambda check, steps: check('run task1' in steps)),
  )
