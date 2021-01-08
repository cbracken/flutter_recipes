# Copyright 2020 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
#
# Recipe to run firebase lab tests.
# This recipe uses the standar flutter dependencies model and a single property
# task_name to identify the test to run.

from contextlib import contextmanager
import re

DEPS = [
    'flutter/repo_util',
    'flutter/flutter_deps',
    'fuchsia/gcloud',
    'fuchsia/gsutil',
    'recipe_engine/context',
    'recipe_engine/file',
    'recipe_engine/path',
    'recipe_engine/properties',
    'recipe_engine/step',
    'recipe_engine/swarming',
]


def RunSteps(api):
  checkout_path = api.path['start_dir'].join('flutter')
  gcs_bucket = 'flutter_firebase_testlab'
  api.repo_util.checkout(
      'flutter',
      checkout_path=checkout_path,
      url=api.properties.get('git_url'),
      ref=api.properties.get('git_ref')
  )
  env, env_prefixes = api.repo_util.flutter_environment(checkout_path)
  deps = api.properties.get('dependencies', [])
  api.flutter_deps.required_deps(env, env_prefixes, deps)
  task_name = api.properties.get('task_name')
  device_flags = [
      '--device', 'model=blueline,version=28', '--device',
      'model=flame,version=29', '--device', 'model=griffin,version=24'
  ]

  with api.context(env=env, env_prefixes=env_prefixes, cwd=checkout_path):
    api.step('flutter doctor', ['flutter', 'doctor', '-v'])
    api.step('download dependencies', ['flutter', 'update-packages'])

  test_path = checkout_path.join('dev', 'integration_tests', task_name)
  with api.step.nest('test_execution') as presentation:
    with api.context(env=env, env_prefixes=env_prefixes, cwd=test_path):
      aab = "build/app/outputs/bundle/release/app-release.aab"
      api.step(
          'Build appbundle', [
              'flutter', 'build', 'appbundle', '--target-platform',
              'android-arm,android-arm64'
          ]
      )
      task_id = api.swarming.task_id
      api.gcloud('--quiet', 'config', 'set', 'project', 'flutter-infra')
      cmd = [
          'firebase', 'test', 'android', 'run', '--type', 'robo', '--app', aab,
          '--timeout', '2m',
          '--results-bucket=gs://%s' % gcs_bucket,
          '--results-dir=%s/%s' % (task_name, task_id)
      ] + device_flags
      api.gcloud(*cmd)
      logcat_path = '%s/%s/*/logcat' % (task_name, task_id)
      tmp_logcat = api.path['cleanup'].join('logcat')
      api.gsutil.download(gcs_bucket, logcat_path, api.path['cleanup'])
      content = api.file.read_text('read', tmp_logcat)
      presentation.logs['logcat'] = content
      api.step('analyze_logcat', ['grep', 'E/flutter', tmp_logcat], ok_ret=(1,))


def GenTests(api):
  yield api.test(
      'basic', api.repo_util.flutter_environment_data(),
      api.properties(task_name='the_task')
  )
