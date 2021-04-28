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
    'flutter/flutter_deps',
    'flutter/repo_util',
    'flutter/retry',
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

  physical_devices = [
      # Physical devices - use only highly available devices to avoid timeouts.
      # Pixel 3
      '--device', 'model=blueline,version=28',
      # Pixel 4
      '--device', 'model=flame,version=29',
      # Moto Z XT1650
      '--device', 'model=griffin,version=24',
  ]

  virtual_devices = [
      # Virtual devices for API level coverage.
      '--device', 'model=Nexus5,version=19',
      # SDK 20 not available virtually or physically.
      '--device', 'model=Nexus5,version=21',
      '--device', 'model=Nexus5,version=22',
      '--device', 'model=Nexus5,version=23',
      # SDK 24 is run on a physical griffin/Moto Z above.
      '--device', 'model=Nexus6P,version=25',
      '--device', 'model=Nexus6P,version=26',
      '--device', 'model=Nexus6P,version=27',
      # SDK 28 is run on a physical blueline/Pixel 3 above.
      # SDK 29 is run on a physical flame/Pixel 4 above.
      '--device', 'model=NexusLowRes,version=30',
  ]

  test_configurations = (
      (
          'Build appbundle',
          ['flutter', 'build', 'appbundle', '--target-platform',
                'android-arm,android-arm64'],
          'build/app/outputs/bundle/release/app-release.aab',
          physical_devices
      ),
      (
          'Build apk',
          ['flutter', 'build', 'apk', '--debug', '--target-platform',
                'android-x86'],
          'build/app/outputs/flutter-apk/app-debug.apk',
          virtual_devices
      ),
  )

  with api.context(env=env, env_prefixes=env_prefixes, cwd=checkout_path):
    api.step('flutter doctor', ['flutter', 'doctor', '-v'])
    api.step('download dependencies', ['flutter', 'update-packages'])

  test_path = checkout_path.join('dev', 'integration_tests', task_name)
  with api.step.nest('test_execution') as presentation:
    with api.context(env=env, env_prefixes=env_prefixes, cwd=test_path):
      task_id = api.swarming.task_id
      api.gcloud('--quiet', 'config', 'set', 'project', 'flutter-infra')
      for step_name, build_command, binary, devices in test_configurations:
        api.step(step_name, build_command)
        firebase_cmd = [
            'firebase', 'test', 'android', 'run', '--type', 'robo',
            '--app', binary,
            '--timeout', '2m',
            '--results-bucket=gs://%s' % gcs_bucket,
            '--results-dir=%s/%s' % (task_name, task_id)
        ] + devices
        # See https://firebase.google.com/docs/test-lab/android/command-line#script_exit_codes
        # If the firebase command fails with 1, it's likely an HTTP issue that
        # will resolve on a retry. If it fails on 15 or 20, it's explicitly
        # an infra failure on the FTL side, so we should just retry.
        def run_firebase():
          return api.gcloud(*firebase_cmd)
        api.retry.wrap(
          run_firebase,
          max_attempts=3,
          retriable_ret=(1, 15, 20))

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

  yield api.test(
      'failure 15', api.repo_util.flutter_environment_data()
  ) + api.step_data(
     'test_execution.gcloud firebase', retcode=15
  )

  yield api.test(
      'failure 10', api.repo_util.flutter_environment_data()
  ) + api.step_data(
     'test_execution.gcloud firebase', retcode=10
  )
