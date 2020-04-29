# Copyright 2020 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from recipe_engine.recipe_api import Property

DEPS = [
    'depot_tools/git',
    'recipe_engine/buildbucket',
    'recipe_engine/context',
    'recipe_engine/json',
    'recipe_engine/path',
    'recipe_engine/properties',
    'recipe_engine/step',
    'yaml',
]

PROPERTIES = {
    'task_name': Property(kind=str, help='Name of the devicelab task to run'),
}


def RunSteps(api, task_name):
  # Checkout the flutter/flutter repository.
  flutter_git_url = 'https://chromium.googlesource.com/external/github.com/flutter/flutter'
  if 'git_url' in api.properties:
    flutter_git_url = api.properties['git_url']

  flutter_git_ref = 'master'
  if 'git_ref' in api.properties:
    flutter_git_ref = api.properties['git_ref']

  api.git.checkout(
      flutter_git_url,
      ref=flutter_git_ref,
      recursive=True,
      set_got_revision=True,
      tags=True)

  # Figure out paths.
  start_path = api.path['start_dir']
  flutter_path = start_path.join('flutter')
  devicelab_path = flutter_path.join('dev', 'devicelab')
  dart_bin = flutter_path.join('bin', 'cache', 'dart-sdk', 'bin')
  flutter_bin = flutter_path.join('bin')

  # Read the manifest.
  manifest_yaml_path = devicelab_path.join('manifest.yaml')
  result = api.yaml.read('read manifest', manifest_yaml_path, api.json.output())
  manifest = result.json.output

  # Verify the manifest contains the task to run.
  if task_name not in manifest['tasks']:
    raise ValueError('Unknown task: %s' % task_name)

  env = {
      # Setup our own pub_cache to not affect other bots on this machine,
      # and so that the pre-populated pub cache is contained in the package.
      'PUB_CACHE': api.path['cache'].join('.pub-cache'),
  }
  env_prefixes = {'PATH': [flutter_bin, dart_bin]}
  with api.context(env=env, env_prefixes=env_prefixes, cwd=devicelab_path):
    api.step('flutter doctor', cmd=['flutter', 'doctor'])
    api.step('pub get', cmd=['pub', 'get'])
    api.step('run ' + task_name, cmd=['dart', 'bin/run.dart', '-t', task_name])


def GenTests(api):
  example_manifest = {"tasks": {"task1": {}, "task2": {}}}
  yield api.test(
      'missing_task_name',
      api.expect_exception('ValueError'),
  )
  yield api.test(
      'unknown_task',
      api.properties(task_name='unknown_task'),
      api.step_data('read manifest.parse', api.json.output(example_manifest)),
      api.expect_exception('ValueError'),
  )
  yield api.test(
      'example_task',
      api.properties(git_ref='refs/pull/123/head'),
      api.properties(task_name='task1'),
      api.step_data('read manifest.parse', api.json.output(example_manifest)),
  ) + api.post_check(lambda check, steps: check('run task1' in steps))
